import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { GamePage } from '../App'

const player = { id: 1, username: 'player', role: 'USER' as const }
const initialGame = {
  id: 1,
  date: '2026-11-10',
  status: 'playing' as const,
  attempts: 0,
  guesses: [],
  answer: null,
}

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderGame() {
  return render(
    <BrowserRouter>
      <GamePage user={player} />
    </BrowserRouter>,
  )
}

describe('daily game', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/games/today/guess')) {
        const body = JSON.parse(String(init?.body)) as { guess: string }
        if (body.guess === 'qwert') {
          return response({ detail: 'That word is not in the five-letter guess list' }, 422)
        }
        return response({
          ...initialGame,
          status: 'won',
          attempts: 1,
          guesses: [{ word: body.guess, result: 'GGGGG' }],
          answer: 'crane',
        })
      }
      if (url.endsWith('/games/today')) return response(initialGame)
      if (url.endsWith('/puzzles/today')) return response({ date: initialGame.date })
      throw new Error(`Unexpected request: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)
  })

  it('renders exactly 30 tiles in six rows of five', async () => {
    renderGame()
    await screen.findByRole('region', { name: 'Wordle game board' })
    expect(document.querySelectorAll('.board .tile')).toHaveLength(30)
  })

  it('submits a physical keyboard guess to the server and locks a completed game', async () => {
    renderGame()
    await screen.findByRole('region', { name: 'Wordle game board' })
    await screen.findByText(initialGame.date)
    for (const key of 'crane') fireEvent.keyDown(window, { key })
    fireEvent.keyDown(window, { key: 'Enter' })

    await screen.findByText('Excellent!')
    const submission = fetchMock.mock.calls.find(([url]) =>
      String(url).endsWith('/games/today/guess'),
    )
    expect(JSON.parse(String(submission?.[1]?.body))).toEqual({ guess: 'crane' })
    expect(document.querySelectorAll('.board .tile-g')).toHaveLength(5)
    expect((screen.getByRole('button', { name: 'Q' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('shows the server validation error for an invalid on-screen guess', async () => {
    renderGame()
    await screen.findByRole('region', { name: 'Wordle game board' })
    await screen.findByText(initialGame.date)
    for (const key of 'QWERT') fireEvent.click(screen.getByRole('button', { name: key }))
    fireEvent.click(screen.getByRole('button', { name: 'ENTER' }))
    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toContain(
        'That word is not in the five-letter guess list',
      )
    })
    expect(document.querySelectorAll('.board .tile')).toHaveLength(30)
  })
})
