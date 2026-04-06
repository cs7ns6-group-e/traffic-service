from setuptools import find_packages, setup

setup(
    name="trafficbook-shared",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.110.0",
        "pydantic>=2.6.0",
        "pydantic-settings>=2.2.0",
        "sqlalchemy[asyncio]>=2.0.0",
        "pyjwt>=2.8.0",
        "httpx>=0.27.0",
        "redis>=5.0.0",
        "pika>=1.3.2",
    ],
)
