import uvicorn

from api.create_app import create_app
from config import config

app = create_app(config)

if __name__ == "__main__":
    uvicorn.run("api.run:app", host="0.0.0.0", port=8000, workers=config.WORKERS, reload=config.IS_DEBUG)
