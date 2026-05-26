import { NextResponse } from 'next/server'

export async function GET() {
  try {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/local-files`)
    if (!res.ok) {
      throw new Error('Failed to fetch local files')
    }
    const data = await res.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error fetching local files:', error)
    return NextResponse.json({ error: 'Failed to fetch local files' }, { status: 500 })
  }
}