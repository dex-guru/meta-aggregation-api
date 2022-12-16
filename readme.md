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
python rest_api/run.py

```

### Dockerized

You can start the project with docker using this command:

```bash
docker-compose -f deploy/docker-compose.yml --project-directory . up --build
```

This command exposes the web application on port 8000, mounts current directory and enables autoreload.

# Architecture

API is build using (Fast API)[https://fastapi.tiangolo.com/] framework, the request
processing consists of VIEW (API routes) - SERVICE - PROVIDERS route, where one request
could be serviced by one provider (if selected) or many with response processing and
collapsing logic developed in Service layer.

## Project structure

```bash
$ tree -d meta_aggregation_api
├── clients
│   └── blockchain # web3 client
├── config # app configuration defenitions
├── models # models used
├── providers # dex aggregators providers logic
├── rest_api
│   ├── middlewares
│   └── routes # API routes
├── services
├── tests # tests
└── utils
```

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

Services also using DEX Guru SDK https://github.com/dex-guru/dg-sdk-python to resolve prices/chains from
DEX Guru Public API.

### Clients Layer

Clients are used to communicate with external providers. Clients are represented by **_api.clients_** module:

* **_api.clients.blockchain_** module contains logic of communication with blockchain nodes via Web3.
* **_api.clients.apm_client_** module contains logic of communication with DEX Guru Public API.
* **_provider_clients_** module contains logic of communication with DEX Aggregators.

Clients are imported in **_api.create_app_** and used in Service layer.

# Contributing

We would be happy to have contributors onboard. No contribution is to small no matter
what it is, it could be adding of support for another provider, bug fixes, new features
or whatever. You can also make API better by Opening issues or providing additional details
on Existing issues.

### Adding New Providers

#### 1. Add Provider's config

Provider's config is a JSON with provider's name, display name and supported chains.
Every chain is an object with spender address for market order and limit order.

If provider doesn't support one of order types, then this spender address for this order type should be null.

Config must be named **config.json**.

#### 2. Add Provider class

To add new provider you need to create a new module in providers_clients folder module,
create a class that inherits from BaseProvider and implement all abstract methods.

Providers defining getting price, quote, limit orders, ets interfaces for specific Provider
(DEX aggregator). All provider specific logic should be implemented there.

Providers classes are expected to handle errors as well.

To have the same provider name in all places, add this to the body of your class.

``` python 
with open(Path(__file__).parent / 'config.json') as f:
    PROVIDER_NAME = ujson.load(f)['name']
```

#### 3. Add Provider class to providers_clients/\_\_init__.py dict

We have a storage of all provider classes

### Chains support

As there is a dependency on support for chain on DEX Guru Public API it's limited by chains
returned by (https://api.dev.dex.guru/v1/chain)[https://api.dev.dex.guru/v1/chain] endpoint.

### Testing

```bash
pytest .
```

## Contributors ✨

Thanks goes to these wonderful people ❤:<br><br>
 <a href = "https://github.com/dex-guru/meta-aggregation-api/graphs/contributors">
   <img src = "https://contrib.rocks/image?repo=dex-guru/meta-aggregation-api"/>
 </a>


### Licensing

This project is licensed under the terms of the MIT license.
