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

### Service Layer

### Providers Layer

# Contributing

We would be happy to have contributors onboard. No contribution is to small no matter
what it is, it could be adding of support for another provider, bug fixes, new features
or whatever. You can also make API better by Opening issues or providing additional details
on Existing issues.

### Adding New Providers

### Fixing bugs

### Handling Errors

### Adding New API Routes

### Testing 

```bash
pytest .
```