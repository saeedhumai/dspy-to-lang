import logging
import os
os.environ['USER_AGENT'] = 'myagent'
# Create and configure logger
logger = logging.getLogger('alyla')
logger.setLevel(logging.INFO)

# Create console handler with formatting
console_handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# Add handler to logger
logger.addHandler(console_handler)
