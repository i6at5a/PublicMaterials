# About
This is a sample implementation of tic-tac-toe to demonstrate the workflow processing capabilities of the LangGraph.
It works with just the standard library except for LangGraph.

# How to install

```Console
$ cd ./langgraph_ticatctoe
$ pip install -r requirements.txt
   :
$ pip show langgraph | grep Version
Version: 0.2.53
```


# How to run

To run
```Console
$ python tictactoe_sync.py
thread ID=d4add3ea-aaff-11ef-81dc-00155daf044f
Turn: 1
 c 1     2      3
r+------+------+------+
1|      |      |      |
 |      |      |      |
 |      |      |      |
 +------+------+------+
2|      |      |      |
 |      |      |      |
  :
```


To resume after a suspention, give the thread ID of the game as a parameter.

```Console
$ python tictactoe_sync.py d4add3ea-aaff-11ef-81dc-00155daf044f 
```


# License

MIT License
