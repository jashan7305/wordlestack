import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, Navigate, Route, Routes, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { BarChart3, HelpCircle, LogOut, Settings } from 'lucide-react'
import './App.css'

type Guess = { word: string; result: string }
type Game = { id: number; date: string; status: 'playing' | 'won' | 'lost'; attempts: number; guesses: Guess[]; answer: string | null }
type User = { id: number; username: string; role: 'USER' | 'ADMIN' }
const API = '/api/v1'
const EMPTY_GUESSES: Guess[] = []

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const csrf = document.cookie.split('; ').find((part) => part.startsWith('csrf_cookie='))?.split('=')[1]
  const response = await fetch(`${API}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(csrf ? { 'X-CSRF-Token': decodeURIComponent(csrf) } : {}), ...options.headers },
    ...options,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? 'Something went wrong')
  }
  return response.json() as Promise<T>
}

function Header({ user, onLogout }: { user: User | null; onLogout: () => void }) {
  return <header className="topbar">
    <Link className="brand" to="/">WORDLESTACK</Link>
    <nav aria-label="Main navigation">
      {user && <><Link to="/stats">Statistics</Link><Link to="/leagues">Leagues</Link><Link to="/leaderboard">Leaderboard</Link>{user.role === 'ADMIN' && <Link to="/admin">Admin</Link>}
        <button className="icon-button" onClick={onLogout} aria-label="Sign out" title="Sign out"><LogOut size={18} /></button></>}
      {!user && <><Link to="/login">Sign in</Link><Link to="/register">Create account</Link></>}
    </nav>
  </header>
}

export function GamePage({ user }: { user: User | null }) {
  const [game, setGame] = useState<Game | null>(null)
  const [current, setCurrent] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [help, setHelp] = useState(false)
  const [statsOpen, setStatsOpen] = useState(false)
  const [today, setToday] = useState('')
  const [guessErr, setGuessErr] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    if (!user) return
    void Promise.all([api<Game>('/games/today'), api<{ date: string }>('/puzzles/today')])
      .then(([newGame, puzzle]) => { setGame(newGame); setToday(puzzle.date) })
      .catch((error: Error) => setNotice(error.message))
  }, [user])

  const submit = async () => {
    if (!game || game.status !== 'playing' || current.length !== 5 || busy) return
    setBusy(true); setNotice(''); setGuessErr('')
    try {
      const updated = await api<Game>('/games/today/guess', { method: 'POST', body: JSON.stringify({ guess: current }) })
      setGame(updated); setCurrent('')
      if (updated.status === 'won') setNotice('Excellent!')
      else if (updated.status === 'lost') setNotice(`The word was ${updated.answer?.toUpperCase() ?? ''}`)
    } catch (error) {
      setGuessErr(error instanceof Error ? error.message : 'Could not submit guess')
    } finally { setBusy(false) }
  }

  const press = (key: string) => {
    if (!game || game.status !== 'playing' || busy) return
    if (key === 'ENTER') { void submit(); return }
    if (key === '⌫') { setCurrent((value) => value.slice(0, -1)); return }
    if (/^[A-Z]$/.test(key) && current.length < 5) setCurrent((value) => value + key.toLowerCase())
  }

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Enter') { event.preventDefault(); void submit() }
      else if (event.key === 'Backspace') press('⌫')
      else if (/^[a-z]$/i.test(event.key)) press(event.key.toUpperCase())
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const submitted = game?.guesses ?? EMPTY_GUESSES
  const letters = useMemo(() => {
    const state: Record<string, string> = {}
    for (const guess of submitted) for (let i = 0; i < 5; i++) {
      const letter = guess.word[i]; const result = guess.result[i]
      if (result === 'G' || (result === 'Y' && state[letter] !== 'G') || (!state[letter] && result === 'X')) state[letter] = result
    }
    return state
  }, [submitted])
  if (!user) return <main className="signed-out"><h1>One word. Six tries.</h1><p>Sign in to play today’s WordleStack game and see your League results.</p><Link className="primary-button" to="/login">Sign in to play</Link></main>
  const keyboard = [
    [...'QWERTYUIOP'],
    [...'ASDFGHJKL'],
    ['ENTER', ...'ZXCVBNM', '⌫'],
  ]
  return <main className="game-shell">
    <div className="game-tools">
      <button className="icon-button" aria-label="How to play" onClick={() => setHelp(true)}><HelpCircle /></button>
      <time>{today || game?.date || ''}</time>
      <button className="icon-button" aria-label="Statistics" onClick={() => setStatsOpen(true)}><BarChart3 /></button>
      <button className="icon-button" aria-label="Settings" onClick={() => navigate('/profile')}><Settings /></button>
    </div>
    {notice && <div className="message" role="status">{notice}</div>}
    {guessErr && <div className="message error" role="alert">{guessErr}</div>}
    <section className="board" aria-label="Wordle game board">
      {Array.from({ length: 30 }, (_, tileIndex) => {
        const row = Math.floor(tileIndex / 5)
        const col = tileIndex % 5
        const guess = submitted[row]
        const letter = guess?.word[col] ?? (row === submitted.length ? current[col] : '') ?? ''
        const result = guess?.result[col]
        return <div key={`${row}-${col}`} className={`tile ${result ? `tile-${result.toLowerCase()}` : letter ? 'tile-filled' : ''}`} aria-label={letter ? `Row ${row + 1} letter ${col + 1}: ${letter}` : `Row ${row + 1} letter ${col + 1}`}>
          {letter?.toUpperCase() ?? ''}
        </div>
      })}
    </section>
    <section className="keyboard" aria-label="On-screen keyboard">
      {keyboard.map((row, rowIndex) => <div className="key-row" key={rowIndex}>{row.map((key, index) => <button key={`${key}-${index}`} className={`key ${key.length > 1 ? 'key-wide' : ''} ${letters[key.toLowerCase()] ? `key-${letters[key.toLowerCase()].toLowerCase()}` : ''}`} onClick={() => press(key)} disabled={game?.status !== 'playing' || busy}>{key}</button>)}</div>)}
    </section>
    {help && <Dialog title="How to play" close={() => setHelp(false)}><p>Guess the word in six tries.</p><p>Green means the letter is in the right place. Yellow means it is in the word elsewhere. Grey means it is not in the word.</p></Dialog>}
    {statsOpen && <StatisticsDialog close={() => setStatsOpen(false)} />}
  </main>
}

function Dialog({ title, close, children }: { title: string; close: () => void; children: ReactNode }) {
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) close() }}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><button className="modal-close" onClick={close} aria-label="Close">×</button><h2 id="modal-title">{title}</h2>{children}</section></div>
}

function StatisticsDialog({ close }: { close: () => void }) {
  const stats = useQuery({ queryKey: ['stats', 'me'], queryFn: () => api<Record<string, unknown>>('/stats/me') })
  return <Dialog title="Statistics" close={close}><div className="stats-grid">{['games_played', 'games_won', 'win_percentage', 'current_streak', 'longest_streak', 'total_points'].map((key) => <div key={key}><strong>{String(stats.data?.[key] ?? '—')}</strong><span>{key.replaceAll('_', ' ')}</span></div>)}</div></Dialog>
}

function AuthPage({ mode, onAuth }: { mode: 'login' | 'register'; onAuth: (u: User) => void }) {
  const [username, setUsername] = useState(''); const [password, setPassword] = useState(''); const [error, setError] = useState('')
  const navigate = useNavigate()
  const [search] = useSearchParams()
  const invite = search.get('invite')
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setError('')
    try { onAuth(await api<User>(`/auth/${mode === 'login' ? 'login' : 'register'}${invite ? `?invite=${encodeURIComponent(invite)}` : ''}`, { method: 'POST', body: JSON.stringify({ username, password }) })); navigate('/leagues') }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not sign in') }
  }
  return <main className="page narrow"><h1>{mode === 'login' ? 'Sign in' : 'Create account'}</h1><form onSubmit={(e) => void submit(e)} className="form"><label>Username<input required minLength={3} maxLength={32} value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" /></label><label>Password<input required minLength={10} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} /></label>{error && <p className="error-text">{error}</p>}<button className="primary-button">{mode === 'login' ? 'Sign in' : 'Create account'}</button></form></main>
}

function DataPage({ title, endpoint }: { title: string; endpoint: string }) {
  const result = useQuery({ queryKey: [endpoint], queryFn: () => api<unknown>(endpoint), retry: false })
  const items = result.data
  const records = Array.isArray(items) ? items : typeof items === 'object' && items !== null && 'items' in items && Array.isArray(items.items) ? items.items : null
  const columns = records?.[0] && typeof records[0] === 'object' ? Object.keys(records[0]) : []
  return <main className="page"><h1>{title}</h1>{result.isLoading ? <p>Loading…</p> : result.error ? <p className="error-text">{result.error.message}</p> : records?.length ? <div className="table-scroll"><table><thead><tr>{columns.map((key) => <th key={key}>{key.replaceAll('_', ' ')}</th>)}</tr></thead><tbody>{records.map((record, index) => { const value = record as Record<string, unknown>; return <tr key={index}>{columns.map((key) => <td key={key}>{title === 'Leagues' && key === 'name' ? <Link to={`/leagues/${String(value.id)}`}>{String(value.name)}</Link> : String(value[key] ?? '—')}</td>)}</tr> })}</tbody></table></div> : records ? <p>No results yet.</p> : typeof items === 'object' && items !== null ? <dl className="data-list">{Object.entries(items).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{String(value ?? '—')}</dd></div>)}</dl> : <p>No results yet.</p>}</main>
}

function LeaguePage({ user }: { user: User | null }) {
  const { id = '' } = useParams()
  const [league, setLeague] = useState<{ name: string; description: string } | null>(null)
  const [daily, setDaily] = useState<unknown[]>([])
  const [notPlayed, setNotPlayed] = useState<unknown[]>([])
  const [overall, setOverall] = useState<unknown[]>([])
  const [error, setError] = useState('')
  useEffect(() => { if (!user) return; void Promise.all([api<{ name: string; description: string }>(`/leagues/${id}`), api<{ played: unknown[]; not_played: unknown[] }>(`/leagues/${id}/leaderboard/daily`), api<unknown[]>(`/leagues/${id}/leaderboard/overall`)]).then(([info, day, total]) => { setLeague(info); setDaily(day.played); setNotPlayed(day.not_played); setOverall(total) }).catch((e: Error) => setError(e.message)) }, [id, user])
  const table = (rows: unknown[]) => rows.length ? <div className="table-scroll"><table><thead><tr>{Object.keys(rows[0] as object).map((key) => <th key={key}>{key.replaceAll('_', ' ')}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{Object.entries(row as Record<string, unknown>).map(([key, value]) => <td key={key}>{String(value ?? '—')}</td>)}</tr>)}</tbody></table></div> : <p>No games yet.</p>
  return <main className="page"><p><Link to="/leagues">Leagues</Link></p><h1>{league?.name ?? 'League'}</h1><p>{league?.description}</p>{error && <p className="error-text">{error}</p>}<h2>Today</h2>{table(daily)}{notPlayed.length > 0 && <><h3>Not played</h3>{table(notPlayed)}</>}<h2>Overall</h2>{table(overall)}</main>
}

function AdminPage() {
  const [leagues, setLeagues] = useState<Array<{ id: number; name: string; description: string; archived: boolean }>>([])
  const [users, setUsers] = useState<Array<{ id: number; username: string }>>([])
  const [name, setName] = useState(''); const [description, setDescription] = useState(''); const [error, setError] = useState('')
  const refresh = () => { void api<typeof leagues>('/admin/leagues').then(setLeagues).catch((e: Error) => setError(e.message)); void api<{ items: typeof users }>('/admin/users').then((data) => setUsers(data.items)).catch((e: Error) => setError(e.message)) }
  useEffect(() => { refresh() }, [])
  const create = async (event: FormEvent) => { event.preventDefault(); try { await api('/admin/leagues', { method: 'POST', body: JSON.stringify({ name, description }) }); setName(''); setDescription(''); refresh() } catch (e) { setError(e instanceof Error ? e.message : 'Could not create League') } }
  const archive = async (league: typeof leagues[number]) => { try { await api(`/admin/leagues/${league.id}`, { method: 'PATCH', body: JSON.stringify({ ...league, archived: !league.archived }) }); refresh() } catch (e) { setError(e instanceof Error ? e.message : 'Could not update League') } }
  const addMember = async (leagueId: number, userId: number) => { try { await api(`/admin/leagues/${leagueId}/members`, { method: 'POST', body: JSON.stringify({ user_id: userId }) }); setError('Member added') } catch (e) { setError(e instanceof Error ? e.message : 'Could not add member') } }
  const invite = async (leagueId: number) => { try { const result = await api<{ url: string }>(`/admin/leagues/${leagueId}/invitations`, { method: 'POST' }); await navigator.clipboard.writeText(result.url.startsWith('http') ? result.url : `${window.location.origin}${result.url}`); setError('Invitation link copied') } catch (e) { setError(e instanceof Error ? e.message : 'Could not create invitation') } }
  return <main className="page"><h1>Administration</h1><p><Link to="/admin/users">Manage users</Link></p><h2>Create a League</h2><form className="admin-form" onSubmit={(event) => void create(event)}><input aria-label="League name" placeholder="League name" minLength={2} maxLength={80} value={name} onChange={(event) => setName(event.target.value)} required /><input aria-label="Description" placeholder="Description" value={description} onChange={(event) => setDescription(event.target.value)} /><button className="primary-button">Create League</button></form>{error && <p className="error-text">{error}</p>}<h2>Leagues</h2><div className="table-scroll"><table><thead><tr><th>Name</th><th>Description</th><th>Status</th><th>Add member</th><th>Invitation</th><th>Action</th></tr></thead><tbody>{leagues.map((league) => <tr key={league.id}><td>{league.name}</td><td>{league.description}</td><td>{league.archived ? 'Archived' : 'Active'}</td><td><select aria-label={`Add member to ${league.name}`} defaultValue="" onChange={(event) => { if (event.target.value) void addMember(league.id, Number(event.target.value)) }}><option value="">Choose a user</option>{users.map((person) => <option key={person.id} value={person.id}>{person.username}</option>)}</select></td><td><button className="text-button" onClick={() => void invite(league.id)}>Create link</button></td><td><button className="text-button" onClick={() => void archive(league)}>{league.archived ? 'Restore' : 'Archive'}</button></td></tr>)}</tbody></table></div></main>
}

function AdminUsersPage() {
  const [rows, setRows] = useState<Array<{ id: number; username: string; role: 'USER' | 'ADMIN'; active: boolean }>>([])
  const [error, setError] = useState('')
  const refresh = () => { void api<{ items: typeof rows }>('/admin/users').then((data) => setRows(data.items)).catch((e: Error) => setError(e.message)) }
  useEffect(() => { refresh() }, [])
  const update = async (row: typeof rows[number], change: { active?: boolean; role?: 'USER' | 'ADMIN' }) => { try { await api(`/admin/users/${row.id}`, { method: 'PATCH', body: JSON.stringify(change) }); refresh() } catch (e) { setError(e instanceof Error ? e.message : 'Could not update account') } }
  return <main className="page"><p><Link to="/admin">Administration</Link></p><h1>Users</h1>{error && <p className="error-text">{error}</p>}<div className="table-scroll"><table><thead><tr><th>Username</th><th>Role</th><th>Status</th><th>Actions</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td>{row.username}</td><td>{row.role}</td><td>{row.active ? 'Active' : 'Disabled'}</td><td><button className="text-button" onClick={() => void update(row, { active: !row.active })}>{row.active ? 'Deactivate' : 'Activate'}</button>{' · '}<button className="text-button" onClick={() => void update(row, { role: row.role === 'ADMIN' ? 'USER' : 'ADMIN' })}>{row.role === 'ADMIN' ? 'Make user' : 'Make admin'}</button></td></tr>)}</tbody></table></div></main>
}

function InvitationPage() {
  const { token = '' } = useParams(); const [message, setMessage] = useState('Checking invitation…'); const [league, setLeague] = useState(''); const [error, setError] = useState(''); const navigate = useNavigate()
  useEffect(() => { void api<{ league: { id: number; name: string } }>(`/invitations/${token}`).then((data) => { setLeague(data.league.name); setMessage(`You have been invited to join ${data.league.name}.`) }).catch((e: Error) => setMessage(e.message)) }, [token])
  const accept = async () => { try { await api(`/invitations/${token}/accept`, { method: 'POST' }); navigate('/leagues') } catch (e) { setError(e instanceof Error ? e.message : 'Could not accept invitation') } }
  const signedIn = document.cookie.includes('csrf_cookie=')
  return <main className="page"><h1>League invitation</h1><p>{message}</p>{league && (signedIn ? <button className="primary-button" onClick={() => void accept()}>Join {league}</button> : <div className="invite-actions"><Link to={`/login?invite=${encodeURIComponent(token)}`}>Sign in and join</Link><Link to={`/register?invite=${encodeURIComponent(token)}`}>Create an account and join</Link></div>)}{error && <p className="error-text">{error}</p>}</main>
}

function App() {
  const queryClient = useQueryClient()
  const currentUser = useQuery({ queryKey: ['auth', 'me'], queryFn: () => api<User>('/auth/me'), retry: false })
  const user = currentUser.data ?? null
  const onAuth = (signedInUser: User) => queryClient.setQueryData(['auth', 'me'], signedInUser)
  const logout = async () => { await api('/auth/logout', { method: 'POST' }).catch(() => undefined); queryClient.setQueryData(['auth', 'me'], null) }
  if (currentUser.isLoading) return <div className="app"><Header user={null} onLogout={() => undefined} /><p className="loading">Loading</p></div>
  return <div className="app"><Header user={user} onLogout={() => void logout()} /><Routes>
    <Route path="/" element={<GamePage user={user} />} />
    <Route path="/login" element={user ? <Navigate to="/" /> : <AuthPage mode="login" onAuth={onAuth} />} />
    <Route path="/register" element={user ? <Navigate to="/" /> : <AuthPage mode="register" onAuth={onAuth} />} />
    <Route path="/stats" element={<DataPage title="Statistics" endpoint="/stats/me" />} />
    <Route path="/leagues" element={<DataPage title="Leagues" endpoint="/leagues" />} />
    <Route path="/leagues/:id" element={<LeaguePage user={user} />} />
    <Route path="/leaderboard" element={<DataPage title="Global leaderboard" endpoint="/leaderboard/global" />} />
    <Route path="/profile" element={<main className="page"><h1>Profile</h1><p>{user?.username}</p></main>} />
    <Route path="/admin" element={user?.role === 'ADMIN' ? <AdminPage /> : <Navigate to="/" />} />
    <Route path="/admin/users" element={user?.role === 'ADMIN' ? <AdminUsersPage /> : <Navigate to="/" />} />
    <Route path="/join/:token" element={<InvitationPage />} />
    <Route path="*" element={<main className="page"><h1>Page not found</h1><Link to="/">Return to game</Link></main>} />
  </Routes><footer className="site-footer">WordleStack · A daily word game</footer></div>
}

export default App
