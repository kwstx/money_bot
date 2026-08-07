import httpx
import asyncio

async def test_metrics():
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/metrics")
        print("Status code:", response.status_code)
        print("Metrics content snippet:")
        print(response.text[:500])

if __name__ == "__main__":
    asyncio.run(test_metrics())
