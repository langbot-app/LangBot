"""Regression against FastGPT v4.9.3 observed wire contracts; local HTTP fixture."""
import pytest
from aiohttp import web
from langbot_plugin.api.entities.builtin.rag import RetrievalContext
from test_shared_state import load_plugin, bind, StorageFixture, configuration

@pytest.mark.asyncio
@pytest.mark.parametrize('scores, expected', [([{'type':'embedding','value':0.72,'index':0}],0.72),([{'type':'embedding','value':0.72},{'type':'rerank','value':0.91}],0.91),([],0.0)])
async def test_fastgpt_nested_search_list_and_typed_scores(scores, expected):
    pc,ec=load_plugin('FastGPTConnector')
    async def search(request):
        return web.json_response({'code':200,'data':{'list':[{'id':'seg','q':'real-format','a':'answer','score':scores,'collectionId':'doc'}]}})
    app=web.Application();app.router.add_post('/api/core/dataset/searchTest',search)
    runner=web.AppRunner(app);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
    cfg={**configuration('A'),'api_base_url':f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}'}
    engine=ec();engine.plugin=bind(pc,StorageFixture())
    try:
        result=await engine.retrieve(RetrievalContext(query='q',knowledge_base_id='kb',creation_settings=cfg))
        assert result.total_found==1
        assert result.results[0].content[0].text=='real-format\nanswer'
        assert result.results[0].score==expected
        assert result.results[0].distance==pytest.approx(1-expected)
    finally:await runner.cleanup()

@pytest.mark.asyncio
async def test_fastgpt_delete_uses_delete_query_id_and_saved_credentials():
    pc,ec=load_plugin('FastGPTConnector');seen=[]
    async def delete(request):
        seen.append((request.method,dict(request.query),request.headers.get('Authorization')))
        if request.method!='DELETE' or request.query.get('id')!='upstream-doc':
            return web.json_response({'code':500,'message':'missingParams'})
        return web.json_response({'code':200,'data':None})
    app=web.Application();app.router.add_route('*','/api/core/dataset/collection/delete',delete)
    runner=web.AppRunner(app);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
    cfg={**configuration('A'),'api_base_url':f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}'}
    store=StorageFixture();first=ec();first.plugin=bind(pc,store)
    try:
        await first.on_knowledge_base_create('kb',cfg)
        restarted=ec();restarted.plugin=bind(pc,store)
        assert await restarted.delete_document('kb','upstream-doc') is False
        await restarted._save_document('kb','host-doc', {'upstream_id':'upstream-doc', 'dataset_id':'A', 'status':'created', 'api_base_url':cfg['api_base_url']})
        assert await restarted.delete_document('kb','host-doc')
        assert seen==[('DELETE',{'id':'upstream-doc'},'Bearer A')]
    finally:await runner.cleanup()
