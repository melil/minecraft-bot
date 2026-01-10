#!/bin/bash


echo "Players: $PLAYERS, idle for $((NOW - EMPTY_SINCE)) sec"
echo "=== TRIGGER SAVE & STOP ==="
mcrcon -H 127.0.0.1 -P 25575 -p SuperPassword228 save-all
echo "Save command sent"
sleep 10
# корректно останавливаем сервер
mcrcon -H 127.0.0.1 -P 25575 -p SuperPassword228 stop
echo "Stop command sent"
sleep 30
shutdown -h now
