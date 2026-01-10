#!/bin/bash
# Тестовые данные для парсинга
TEST_OUTPUT="There are 3 of a max of 20 players online: Alex, Steve, Notch"

# Извлекаем количество игроков
if [[ $TEST_OUTPUT =~ There\ are\ ([0-9]+)\ of ]]; then
    echo "Игроков онлайн: ${BASH_REMATCH[1]}"
fi

# Извлекаем имена игроков
if [[ $TEST_OUTPUT =~ players\ online:\ (.+)$ ]]; then
    echo "Игроки: ${BASH_REMATCH[1]}"
fi
