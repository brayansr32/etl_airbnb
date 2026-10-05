import logging
import os
from datetime import datetime

def get_logger(name):
    """Configura y retorna un logger centralizado para todo el proceso ETL."""
    os.makedirs("../logs", exist_ok=True)
    
    # Solo configuramos el root logger si no tiene handlers
    if not logging.getLogger().hasHandlers():
        log_filename = f"../logs/log_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename, encoding='utf-8'), 
                logging.StreamHandler()
            ]
        )
    
    return logging.getLogger(name)
