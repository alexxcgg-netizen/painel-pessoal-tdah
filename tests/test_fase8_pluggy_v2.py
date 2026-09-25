"""pluggy_client.get_transactions usa /v2/transactions com cursor (o /transactions antigo responde 410)."""
from unittest.mock import MagicMock, patch

import pluggy_client


def _resp(body):
    r = MagicMock()
    r.json.return_value = body
    r.raise_for_status.return_value = None
    return r


def test_usa_v2_e_segue_cursor():
    respostas = [_resp({"results": [{"id": "a"}], "next": "c1"}), _resp({"results": [{"id": "b"}], "next": None})]
    with patch.object(pluggy_client, "_headers", return_value={}), \
         patch("pluggy_client.requests.get", side_effect=respostas) as get:
        transacoes, truncado = pluggy_client.get_transactions("acc")
        assert [t["id"] for t in transacoes] == ["a", "b"]
        assert truncado is False
    urls = [c.args[0] for c in get.call_args_list]
    assert all(u.endswith("/v2/transactions") for u in urls)
    assert get.call_args_list[0].kwargs["params"] == {"accountId": "acc"}
    assert get.call_args_list[1].kwargs["params"] == {"accountId": "acc", "cursor": "c1"}


def test_nao_manda_page_nem_pagesize():
    with patch.object(pluggy_client, "_headers", return_value={}), \
         patch("pluggy_client.requests.get", return_value=_resp({"results": [], "next": None})) as get:
        pluggy_client.get_transactions("acc")
    params = get.call_args.kwargs["params"]
    assert "page" not in params and "pageSize" not in params
