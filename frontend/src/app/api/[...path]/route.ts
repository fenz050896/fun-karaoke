import { NextRequest, NextResponse } from 'next/server'

const BACKEND = 'http://backend:8000'

async function proxy(req: NextRequest) {
  const path = req.nextUrl.pathname.replace(/^\/api/, '')
  const url = `${BACKEND}${path}${req.nextUrl.search}`

  try {
    const headers: Record<string, string> = {}
    req.headers.forEach((value, key) => {
      if (!['host', 'connection'].includes(key.toLowerCase())) {
        headers[key] = value
      }
    })

    const res = await fetch(url, {
      method: req.method,
      headers,
      body: req.method !== 'GET' && req.method !== 'HEAD' ? await req.arrayBuffer() : undefined,
    })

    const body = await res.arrayBuffer()
    const responseHeaders: Record<string, string> = {}
    res.headers.forEach((value, key) => {
      if (!['content-encoding', 'transfer-encoding'].includes(key.toLowerCase())) {
        responseHeaders[key] = value
      }
    })

    return new NextResponse(body, {
      status: res.status,
      headers: responseHeaders,
    })
  } catch (error) {
    console.error('API proxy error:', error)
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 502 })
  }
}

export const GET = proxy
export const POST = proxy
export const DELETE = proxy
export const PUT = proxy
export const PATCH = proxy
