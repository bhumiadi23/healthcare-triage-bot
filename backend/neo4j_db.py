"""
Neo4j Connection — Healthcare Triage Bot
Uses the official neo4j async driver
"""
import os, ssl, certifi
from neo4j import AsyncGraphDatabase, AsyncDriver
from dotenv import load_dotenv

load_dotenv()

URI      = os.getenv("NEO4J_URI",      "neo4j://13e3e3f7.databases.neo4j.io")
USER     = os.getenv("NEO4J_USER",     "13e3e3f7")
PASSWORD = os.getenv("NEO4J_PASSWORD", "adp9EytUWD7RgOJIzLBdELIbcsXJHIBj401AgV3ZkRM")

_driver: AsyncDriver = None


async def connect_neo4j() -> AsyncDriver:
    global _driver
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    _driver = AsyncGraphDatabase.driver(URI, auth=(USER, PASSWORD), ssl_context=ssl_ctx)
    await _driver.verify_connectivity()
    print(f"[Neo4j] Connected: {URI}")
    return _driver


async def close_neo4j():
    global _driver
    if _driver:
        await _driver.close()
        print("[Neo4j] Connection closed.")


def get_neo4j() -> AsyncDriver:
    return _driver
