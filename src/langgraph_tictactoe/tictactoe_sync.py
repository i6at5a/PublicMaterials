import random
import re
import sys
import uuid
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from typing import TypedDict, Annotated, Literal, Union


DB_NAME = "tictactoe.sqlite"

__PLAYERS = [
    {"id": "red", "index": -1, "mark": "🔴"},
    {"id": None, "index": 0, "mark": "  "},
    {"id": "blue", "index": 1, "mark": "🔵"}
]


def _update_board(brd: list, pv: Union[list, tuple]) -> list:
    if type(pv) == list:
        brd = pv
    elif type(pv) == tuple:
        brd[pv[0]] = pv[1]
    return brd


def _set_or_append(lst: list, v: Union[list, str]) -> list:
    if type(v) == list:
        return v
    else:
        return lst + [v]


class GameState(TypedDict):
    turn: int
    board: Annotated[list[int], _update_board]
    is_next_playerBLUE: bool
    result: str
    record: Annotated[list[str, int], _set_or_append]


class M2Strategy(TypedDict):
    board: Annotated[list[int], _update_board]
    is_next_playerBLUE: bool
    record: Annotated[list[str, int], _set_or_append]
    m2scores: Annotated[list[int, int], _set_or_append]


class TictactoeConfig(TypedDict):
    thread_id: str
    red: Literal["human", "cpu1", "cpu2"]
    blue: Literal["human", "cpu1", "cpu2"]


def _define_graph(checkpointer):
    # Sub graph
    m2builder = StateGraph(M2Strategy)

    m2builder.add_node("evaluate_cpu2s_option", _evaluate_cpu2s_option)
    m2builder.add_node("select_cpu2s_input", _select_cpu2s_input)

    m2builder.add_conditional_edges(START, _generate_cpu2s_options)
    m2builder.add_edge("evaluate_cpu2s_option", "select_cpu2s_input")

    m2graph = m2builder.compile()

    # Main graph
    builder = StateGraph(GameState, TictactoeConfig)
    builder.add_node("start_turn", _start_turn)
    builder.add_node("get_cpu1s_input", _get_cpu1s_input)
    builder.add_node("get_cpu2s_input", m2graph)
    builder.add_node("get_humans_input", _get_humans_input)
    builder.add_node("end_turn", _end_turn)
    builder.add_node("resume_game", _resume_game)
    builder.add_node("show_result", _show_result)

    builder.add_edge(START, "start_turn")
    builder.add_conditional_edges("start_turn", _select_playertype, {
        "cpu1": "get_cpu1s_input",
        "cpu2": "get_cpu2s_input",
        "human": "get_humans_input"
    })
    builder.add_edge("get_cpu1s_input", "end_turn")
    builder.add_edge("get_cpu2s_input", "end_turn")
    builder.add_conditional_edges("get_humans_input", _is_game_suspended, {
        True: "resume_game",
        False: "end_turn"
    })

    builder.add_conditional_edges("end_turn", _judge_game, {
        "next_turn": "start_turn",
        "game_over": "show_result"
    })
    builder.add_edge("resume_game", "start_turn")
    builder.add_edge("show_result", END)

    return builder.compile(checkpointer=checkpointer, interrupt_before=["resume_game"])


def _start_turn(game: GameState) -> None:
    print(f"Turn: {game['turn']}")
    _show_board(game["board"])
    return


def _get_cpu1s_input(game: GameState) -> dict:
    player = __PLAYERS[game["is_next_playerBLUE"] * 2]

    while True:
        idx = random.randrange(0, 9)
        if game["board"][idx] == 0:
            break

    return {
        "board": (idx, player["index"]),
        "record": (player["index"], idx)
    }


def _generate_cpu2s_options(game: GameState) -> dict:
    board = game["board"]

    def get_indexes_of_unmarked():
        return map(lambda p: p[0], filter(lambda v: v[1] == 0, enumerate(board)))

    return [Send("evaluate_cpu2s_option", n)
            for n in get_indexes_of_unmarked()]


def _evaluate_cpu2s_option(pos_candidate: int):
    return {
        "m2scores": (pos_candidate, random.randrange(0, 100))
    }


def _select_cpu2s_input(m2s: M2Strategy):
    player = __PLAYERS[m2s["is_next_playerBLUE"] * 2]
    option_having_maxscore = (max(m2s["m2scores"], key=lambda s: s[1]))[0]

    return {
        "board": (option_having_maxscore, player["index"]),
        "record": (player["index"], option_having_maxscore),
        "m2scores": []
    }


def _get_humans_input(game: GameState) -> dict:
    player = __PLAYERS[game["is_next_playerBLUE"] * 2]
    re_userinput = re.compile(
        r"\s*((?P<s>[s|S])|(?P<row>\d)\s*,\s*(?P<col>\d))")

    idx = -1
    while True:
        cmd = input(f'Input next position for {player["mark"]} ' +
                    f' in the format "r,c" or "s" to suspend: ')

        m = re_userinput.match(cmd)
        if m is None:
            continue

        if m.group("s"):
            return {
                "result": "Suspended"
            }

        idx = int(m.group("row")) * 3 + int(m.group("col")) - 4

        if game["board"][idx] == 0:
            break

    return {
        "board": (idx, player["index"]),
        "record": (player["index"], idx)
    }


def _end_turn(game: GameState) -> dict:
    player = __PLAYERS[game["is_next_playerBLUE"] * 2]

    last_pos = divmod(game["record"][-1][1], 3)
    print(f"Player {player['mark']} marked position at " +
          f" (r={last_pos[0] + 1}, c={last_pos[1] + 1})")
    print()

    has_3marks = _has_3marks_in_a_row(game["board"], player)
    if has_3marks:
        return {"result": f"{player['mark']} Won"}

    if game["board"].count(0) == 0:
        return {"result": "Draw"}

    return {
        "turn": game["turn"] + 1,
        "is_next_playerBLUE": not game["is_next_playerBLUE"]
    }


def _resume_game(game: GameState) -> dict:
    return {"result": None}


def _show_result(game: GameState) -> None:
    print("-----------------------")
    print("Result:")
    print(f" {game['result']}")
    print("Record:")

    for idx, hst in enumerate(game['record']):
        pos = divmod(hst[1], 3)
        print(
            f" {idx + 1} {__PLAYERS[hst[0] + 1]['mark']} (r={pos[0] + 1}, c={pos[1] + 1})")

    print()
    _show_board(game["board"])
    return


def _select_playertype(game: GameState, config: RunnableConfig) -> str:
    player = __PLAYERS[game["is_next_playerBLUE"] * 2]
    return config["configurable"][player["id"]]


def _is_game_suspended(game: GameState) -> str:
    return game["result"] == "Suspended"


def _judge_game(game: GameState) -> str:
    if game["result"] is None:
        return "next_turn"
    else:
        return "game_over"


def _show_board(board: list[int]) -> None:

    def c(rows):
        return tuple([__PLAYERS[r + 1]["mark"] for r in rows])

    for l in [
        " c 1     2      3",
        "r+------+------+------+",
        "1|      |      |      |",
        " |  %s  |  %s  |  %s  |" % c(board[0:3]),
        " |      |      |      |",
        " +------+------+------+",
        "2|      |      |      |",
        " |  %s  |  %s  |  %s  |" % c(board[3:6]),
        " |      |      |      |",
        " +------+------+------+",
        "3|      |      |      |",
        " |  %s  |  %s  |  %s  |" % c(board[6:9]),
        " |      |      |      |",
        " +------+------+------+",
    ]:
        print(l)
    print()


def _has_3marks_in_a_row(board: list[int], player: dict) -> bool:
    full_score = player["index"] * 3
    for pos in [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],
        [0, 3, 6], [1, 4, 7], [2, 5, 8],
        [2, 4, 6], [0, 4, 8]
    ]:
        if sum(map(lambda idx: board[idx], pos)) == full_score:
            return True

    return False


def run(thread_id):
    if thread_id is None:

        init_vals = {
            "turn": 1,
            "board": [0, 0, 0, 0, 0, 0, 0, 0, 0],
            "is_next_playerBLUE": False,
            "record": [],
            "result": None,
            "m2scores": []
        }
        thread_id = str(uuid.uuid1())
    else:
        init_vals = None

    with SqliteSaver.from_conn_string(DB_NAME) as chkpointer:
        game_graph = _define_graph(chkpointer)

        print(f"thread ID={thread_id}")
        game_graph.invoke(init_vals,
                          config={
                              "recursion_limit": 40,
                              "configurable": {
                                  "thread_id": thread_id,
                                  "red": "human",
                                  "blue": "cpu2",
                              }
                          }, debug=False)


if __name__ == '__main__':
    if 1 < len(sys.argv):
        run(sys.argv[1])
    else:
        run(None)
