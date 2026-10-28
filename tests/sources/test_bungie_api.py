import json

from shell.sources import bungie_api as api
from shell.sources.sheets import fetch

REF = "#/components/schemas/"

SPEC = {
    "info": {"version": "9.9.9"},
    "paths": {
        "/Destiny2/{membershipType}/Profile/{id}/": {"get": {
            "tags": ["Destiny2"], "operationId": "Destiny2.GetProfile", "description": "Profile\r\ninfo.",
            "parameters": [
                {"name": "components", "in": "query", "schema": {"type": "array", "items": {
                    "type": "integer", "x-enum-reference": {"$ref": REF + "Destiny.DestinyComponentType"}}}},
                {"name": "id", "in": "path", "required": True, "schema": {"type": "integer", "format": "int64"}},
            ],
            "responses": {"200": {"$ref": "#/components/responses/Profile"}},
        }},
        "/Destiny2/Actions/Items/EquipItem/": {"post": {
            "tags": ["Destiny2"], "operationId": "Destiny2.EquipItem",
            "requestBody": {"content": {"application/json": {"schema": {"$ref": REF + "Destiny.Requests.Req"}}}},
            "responses": {"200": {"$ref": "#/components/responses/int32"}},
            "security": [{"oauth2": ["MoveEquipDestinyItems"]}],
            "x-documentation-attributes": {"ThrottleSecondsBetweenActionPerUser": "0.1"},
        }},
    },
    "components": {
        "responses": {
            "Profile": {"content": {"application/json": {"schema": {"properties": {
                "Response": {"$ref": REF + "Destiny.Responses.DestinyProfileResponse"}}}}}},
            "int32": {"content": {"application/json": {"schema": {"properties": {
                "Response": {"type": "integer", "format": "int32"}}}}}},
        },
        "schemas": {
            "Destiny.DamageType": {"type": "integer", "x-enum-values": [
                {"numericValue": 0, "identifier": "None"}, {"numericValue": 2, "identifier": "Arc"}]},
            "Destiny.Definitions.DestinyInventoryItemDefinition": {
                "type": "object", "x-mobile-manifest-name": "Items", "properties": {
                    "collectibleHash": {"type": "integer", "format": "uint32", "nullable": True,
                                        "x-mapped-definition": {"$ref": REF + "Destiny.Definitions.Coll"}},
                    "stats": {"type": "object", "additionalProperties": {"$ref": REF + "Destiny.Stat"},
                              "x-dictionary-key": {"type": "integer", "format": "uint32"}},
                }},
            "Destiny.Responses.DestinyProfileResponse": {"type": "object", "properties": {
                "profileInventory": {"allOf": [{"$ref": REF + "SingleComponentResponseOfInv"}],
                                     "description": "Items.\r\nCOMPONENT TYPE: ProfileInventories",
                                     "x-destiny-component-type-dependency": "ProfileInventories"}}},
            "SingleComponentResponseOfInv": {"type": "object", "properties": {}},
            "User.GeneralUser": {"type": "object", "properties": {"displayName": {"type": "string"}}},
        },
    },
}


def test_type_str():
    t = api.type_str
    assert t({"type": "integer", "format": "uint32", "nullable": True,
              "x-mapped-definition": {"$ref": REF + "X.Def"}}) == "uint32 → X.Def?"
    assert t({"type": "array", "items": {"type": "integer", "x-enum-reference": {"$ref": REF + "E"},
                                         "x-enum-is-bitmask": True}}) == "(enum E (bitmask))[]"
    assert t({"type": "object", "additionalProperties": {"type": "string"}}) == "map<string, string>"
    assert t({"type": "string", "format": "date-time"}) == "date-time"


def test_group_schemas_merges_small_namespaces():
    names = [f"Destiny.Definitions.Sockets.S{i}" for i in range(5)] + [
        "Destiny.Definitions.Lore.L", "Destiny.Misc.Color", "Destiny.DamageType",
        "SingleComponentResponseOfX", "BungieMembershipType", "User.GeneralUser"]
    groups = api.group_schemas(names)
    assert len(groups["Destiny.Definitions.Sockets"]) == 5
    # Lore (1) joins Destiny.Definitions, which stays small and joins Destiny in turn
    assert "Destiny.Definitions" not in groups
    assert sorted(groups["Destiny"]) == ["Destiny.DamageType", "Destiny.Definitions.Lore.L", "Destiny.Misc.Color"]
    assert groups["Generics"] == ["SingleComponentResponseOfX"]
    assert sorted(groups["BungieNet"]) == ["BungieMembershipType", "User.GeneralUser"]


def test_build_renders_endpoints_and_schemas():
    files = api.build(SPEC, "2026-01-01")
    assert set(files) == {"index.md", "endpoints-destiny2.md", "schemas-destiny.md", "schemas-generics.md",
                          "schemas-bungienet.md"}
    ep = files["endpoints-destiny2.md"]
    assert "### Destiny2.GetProfile\n\n`GET /Destiny2/{membershipType}/Profile/{id}/`\n\nProfile info." in ep
    assert "- `id` (path, `int64`, required)" in ep  # path parameters first
    assert ep.index("`id`") < ep.index("`components`")
    assert "Response: `Destiny.Responses.DestinyProfileResponse`" in ep
    assert "OAuth required, scopes: `MoveEquipDestinyItems`" in ep
    assert "Body: `Destiny.Requests.Req`" in ep and "Response: `int32`" in ep
    sc = files["schemas-destiny.md"]
    assert "### Destiny.DamageType (enum)\n\n- `0` None\n- `2` Arc\n" in sc
    assert "table `DestinyInventoryItemDefinition` (mobile: `Items`)" in sc
    assert "- `collectibleHash` (`uint32 → Destiny.Definitions.Coll?`)" in sc
    assert "- `stats` (`map<uint32, Destiny.Stat>`)" in sc
    assert "— Items. [component: ProfileInventories]" in sc
    assert "Bungie API 9.9.9" in files["index.md"] and "[schemas-destiny.md](schemas-destiny.md)" in files["index.md"]


def test_refresh_writes_removes_stale_and_reports_changes(monkeypatch):
    monkeypatch.setattr(fetch, "_get", lambda url: json.dumps(SPEC).encode())
    api.folder().mkdir(parents=True)
    (api.folder() / "schemas-obsolete.md").write_text("old", encoding="utf-8")
    first = api.refresh()
    assert first["ok"] and "index.md" in first["changed"] and first["stale"] == []
    assert not (api.folder() / "schemas-obsolete.md").exists()
    assert (api.folder() / "endpoints-destiny2.md").exists()
    assert api.refresh()["changed"] == []


def test_refresh_serves_stale_spec_on_bad_download(monkeypatch):
    monkeypatch.setattr(fetch, "_get", lambda url: json.dumps(SPEC).encode())
    api.refresh()
    monkeypatch.setattr(fetch, "_get", lambda url: b"<html>")
    report = api.refresh(force=True)
    assert report["ok"] and report["stale"] == ["openapi.json"]


def test_refresh_without_cache_or_network_fails(monkeypatch):
    def boom(url):
        raise OSError("offline")

    monkeypatch.setattr(fetch, "_get", boom)
    report = api.refresh()
    assert not report["ok"] and "spec download failed" in report["errors"][0]


def test_valid():
    assert api._valid(json.dumps(SPEC))
    assert not api._valid("<html>")
    assert not api._valid("{}")
