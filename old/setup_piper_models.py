#!/usr/bin/env python3

import os
from pathlib import Path
import requests
from tqdm import tqdm
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("setup")

def setup_models():
    # Define model paths and URLs
    models_dir = Path("./piper-models")
    base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/sv/sv_SE/nst/medium"
    models = {
        "model": "sv_SE-nst-medium.onnx",
        "config": "sv_SE-nst-medium.onnx.json"
    }

    # Create models directory
    models_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created models directory: {models_dir}")

    # Download each model file
    for model_type, filename in models.items():
        output_path = models_dir / filename
        
        if output_path.exists():
            logger.info(f"{model_type} file already exists: {output_path}")
            continue

        url = f"{base_url}/{filename}"
        logger.info(f"Downloading {model_type} from {url}")

        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            with open(output_path, 'wb') as f, tqdm(
                desc=filename,
                total=total_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
            ) as pbar:
                for data in response.iter_content(chunk_size=8192):
                    size = f.write(data)
                    pbar.update(size)
            
            logger.info(f"Successfully downloaded {model_type}")
            
        except Exception as e:
            logger.error(f"Error downloading {model_type}: {e}")
            if output_path.exists():
                output_path.unlink()
            raise

    logger.info("Model setup completed successfully")
    return True

if __name__ == "__main__":
    try:
        setup_models()
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        exit(1)