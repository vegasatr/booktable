#!/usr/bin/env python3
import subprocess
import sys
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    filename='logs/git_rollback.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def rollback_to_previous():
    try:
        # Получаем хеш предыдущего коммита
        result = subprocess.run(['git', 'log', '-2', '--pretty=format:%H'], 
                              capture_output=True, text=True)
        commits = result.stdout.strip().split('\n')
        
        if len(commits) < 2:
            logging.error("Недостаточно коммитов для отката")
            print("Ошибка: Недостаточно коммитов для отката")
            return False
            
        previous_commit = commits[1]
        
        # Выполняем откат
        subprocess.run(['git', 'reset', '--hard', previous_commit], check=True)
        logging.info(f"Успешный откат к коммиту {previous_commit}")
        print(f"✅ Успешный откат к предыдущей версии (коммит: {previous_commit})")
        return True
        
    except subprocess.CalledProcessError as e:
        logging.error(f"Ошибка при выполнении Git-команды: {str(e)}")
        print(f"❌ Ошибка при откате: {str(e)}")
        return False
    except Exception as e:
        logging.error(f"Непредвиденная ошибка: {str(e)}")
        print(f"❌ Непредвиденная ошибка: {str(e)}")
        return False

if __name__ == "__main__":
    logging.info("Запуск скрипта отката")
    rollback_to_previous() 