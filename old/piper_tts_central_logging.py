import logging
from typing import Optional

from fastapi import FastAPI

class LoggingManager:
    """Centralized logging configuration manager"""
    _initialized = False
    
    @classmethod
    def setup_logging(cls, debug: bool = False) -> None:
        """Configure logging globally"""
        if cls._initialized:
            return
            
        # Set the root logger level
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG if debug else logging.INFO)
        
        # Remove any existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        
        # Add handler to root logger
        root_logger.addHandler(console_handler)
        
        cls._initialized = True
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """Get a logger with the specified name"""
        if not cls._initialized:
            cls.setup_logging()
        return logging.getLogger(name)

# Update PiperTTSService class to use the logging manager
class PiperTTSService:
    def __init__(self, config: Optional[PiperConfig] = None):
        """Initialize service with optional configuration"""
        self.config = config or PiperConfig()
        self.logger = LoggingManager.get_logger("PiperTTSService")
        
        # Initialize AudioDeviceManager first
        self.audio_manager = AudioDeviceManager(self.logger)
        
        # Rest of the initialization code...
    
    def _setup_logger(self) -> logging.Logger:
        """This method is now deprecated and just returns the existing logger"""
        return self.logger

# Update AudioDeviceManager to use the logging manager
class AudioDeviceManager:
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        # Rest of the initialization...

# Update other classes similarly
class PiperTTSServiceWrapper:
    def __init__(self, config: Optional[PiperConfig] = None):
        self.logger = LoggingManager.get_logger("PiperTTSServiceWrapper")
        self.tts_service = PiperTTSService(config)
        # Rest of the initialization...

# Update the FastAPI app setup
def setup_app_logging():
    LoggingManager.setup_logging(debug=False)
    return LoggingManager.get_logger("app.timing")

# In your FastAPI app initialization
setup_logging = setup_app_logging()
app = FastAPI(lifespan=lifespan)

@app.middleware("http")
async def add_timing_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # Use the logger from the logging manager
    logger = LoggingManager.get_logger("app.timing")
    logger.info(
        f"{request.method} {request.url.path} completed in {process_time:.3f}s"
    )
    return response