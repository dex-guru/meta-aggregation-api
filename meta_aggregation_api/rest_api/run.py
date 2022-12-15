import uvicorn

from meta_aggregation_api.rest_api.create_app import create_app
from meta_aggregation_api.config import config

app = create_app(config)

if __name__ == "__main__":
    uvicorn.run("rest_api.run:app", host="0.0.0.0", port=8000, reload=config.IS_DEBUG)
