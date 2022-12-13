# DEX Guru Trading Api 

API serves as a DEX aggregators gateway and bargains finder (best quote) between
assets and provides unified interface wrapping up differences between different
aggregators. 

User request price, getting sorted list of quotes and bargain calcs,
and can request a quote (with tx data included) for selected bargain.

# Getting started

ENV Dependencies:

* Python 3.10
* pip

to run:

```bash
pip install -r requirements.txt
python api/run.py

```

### Dockerized 

```bash
docker-compose up 
```

# Architecture

API is build using (Fast API)[https://fastapi.tiangolo.com/] framework, the request
processing consists of VIEW (API routes) - SERVICE - PROVIDERS route, where one request
could be serviced by one provider (if selected) or many with response processing and
collapsing logic developed in Service layer.

TODO: ADD CHART HERE

### API Layer

Routes representing user's actions (request price, quote, gas) are **_api.routes_** and imported
via **_api.create_app_**. We are using FastAPI Framework, which is based on Starlette/ASGI.
FastAPI provides automatic documentation (Swagger) and validation of requests/responses. Available at 
API root, so after starting it via `python api/run.py` you can access it at http://localhost:8000/docs.

### Service Layer

As API operates as aggregation proxy for DEX aggregators, there is logic of requests chaining and 
response processing in Service layer. Service layer is represented by **_api.service_** module.

* **_api.service.chains_** module allows us to build chains metadata config object used in other services.
* **_api.service.meta_aggregation_service_** module contains logic of users requests processing and against 
providers responses and collapsing those.
* **_api.service.gas_service_** module contains logic processing requests for gas price and gas estimation.

Services are imported in **_api.create_app_** and used in API routes. They're routing requests to externals providers 
such as Web3(Blockchain Nodes), DEX Guru Public API, and DEX Aggregators. Calculating the best bargain across 
aggregators supported and returning results to user via API Layer.

### Clients Layer

Clients are used to communicate with external providers. Clients are represented by **_api.clients_** module:

* **_api.clients.web3_client_** module contains logic of communication with blockchain nodes via Web3.
* **_api.clients.dex_guru_client_** module contains logic of communication with DEX Guru Public API.
* **_api.clients.dex_aggregators_client_** module contains logic of communication with DEX Aggregators.
* **_api.clients.gas_client_** module contains logic of communication with Gas Station API.
* **_api.clients.etherscan_client_** module contains logic of communication with Etherscan API.

Clients are imported in **_api.create_app_** and used in Service layer.

# Contributing

We would be happy to have contributors onboard. No contribution is to small no matter
what it is, it could be adding of support for another provider, bug fixes, new features
or whatever. You can also make API better by Opening issues or providing additional details
on Existing issues.

### Adding New Providers

To add new provider you need to create a new module in providers_clients folder module,
create a class that inherits from BaseProvider and implement all abstract methods. 

Providers defining getting price, quote, limit orders, ets interfaces for specific Provider
(DEX aggregator). All provider specific logic should be implemented there.

Providers classes are expected to handle errors as well.

### Chains support

As there is a dependency on support for chain on DEX Guru Public API it's limited by chains
returned by (https://api.dev.dex.guru/v1/chain)[https://api.dev.dex.guru/v1/chain] endpoint.

### Fixing bugs

### Handling Errors

### Adding New API Routes

### Testing 

```bash
pytest .
```