from httpx import AsyncClient


async def test_create_bucket_success(client: AsyncClient):
    response = await client.post("api/v1/buckets", json={"name": "mybucket"})
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "mybucket"
    assert "id" in data


async def test_name_conflict(client: AsyncClient):
    first = await client.post("api/v1/buckets", json={"name": "mybucket"})
    assert first.status_code == 201

    second = await client.post('api/v1/buckets', json={'name': 'mybucket'})
    assert second.status_code == 409


async def test_wrong_name_cause(client: AsyncClient):
    response = await client.post('api/v1/buckets', json={'name': 's'})
    assert response.status_code == 422