import asyncio

import aiocoap


async def main() -> None:
    ctx = await aiocoap.Context.create_client_context()

    request = aiocoap.Message(code=aiocoap.GET, uri="coap://127.0.0.1/hello")
    request2 = aiocoap.Message(code=aiocoap.POST, uri="coap://127.0.0.1/double", payload=b'16')

    try:
        response = await ctx.request(request).response
        print(response.payload.decode())

        response2 = await ctx.request(request2).response
        print(response2.payload.decode())

    except Exception as exc:
        print(f"Request failed: {exc}")


asyncio.run(main())
