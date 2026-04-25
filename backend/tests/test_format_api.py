from __future__ import annotations


def test_smiles_to_svg_returns_svg_payload(client):
    response = client.post("/api/format/smiles-to-svg", json={"struct": "c1ccccc1"})

    assert response.status_code == 200
    body = response.json()
    assert "<svg" in body["svg"]
    assert "</svg>" in body["svg"]


def test_smiles_to_svg_rejects_invalid_smiles(client):
    response = client.post("/api/format/smiles-to-svg", json={"struct": "not-a-smiles"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid SMILES structure."
