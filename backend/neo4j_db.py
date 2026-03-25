"""
Neo4j Connection — Healthcare Triage Bot
Uses the official neo4j async driver
"""
import os, ssl, certifi
from neo4j import AsyncGraphDatabase, AsyncDriver
from dotenv import load_dotenv

load_dotenv()

URI      = os.getenv("NEO4J_URI")
USER     = os.getenv("NEO4J_USER")
PASSWORD = os.getenv("NEO4J_PASSWORD")

if not all([URI, USER, PASSWORD]):
    raise RuntimeError("NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD must be set in .env")

_driver: AsyncDriver = None


async def connect_neo4j() -> AsyncDriver:
    global _driver
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
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
