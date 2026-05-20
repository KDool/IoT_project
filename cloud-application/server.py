import asyncio, aiocoap

from urllib3 import request
import aiocoap.resource as resource # type: ignore

class HelloResource(resource.ObservableResource):

    async def render_get(self, request):
        return aiocoap.Message(payload=b'Hello')

    async def render_post(self, request):
        value = int(request.payload)
        result = value ** 0.5
        return aiocoap.Message(
            code=aiocoap.CHANGED,
            payload=str(result).encode()
            ) 
class DoubleResource(resource.ObservableResource):

    async def render_get(self, request):
        return aiocoap.Message(payload=b'Square')

    async def render_post(self, request):
        value = int(request.payload)
        result = value * 2
        return aiocoap.Message(
            code=aiocoap.CHANGED,
            payload=str(result).encode()
            )



async def main():
    root = resource.Site()
    root.add_resource(['.well-known', 'core'],
                        resource.WKCResource(root.get_resources_as_linkheader))
    root.add_resource(['hello'], HelloResource())
    root.add_resource(['double'], DoubleResource())
    await aiocoap.Context.create_server_context(root)
    await asyncio.get_running_loop().create_future()

asyncio.run(main())