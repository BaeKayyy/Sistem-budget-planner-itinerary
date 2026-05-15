import { useMemo, useState } from 'react'
import './App.css'

const API_BASE_URL = 'http://127.0.0.1:8000'

const defaultAllocation = {
  hotel: 30,
  wisata: 25,
  kuliner: 20,
  oleh_oleh: 15,
  transport: 10,
}

const categories = [
  ['hotel', 'Hotel'],
  ['wisata', 'Wisata'],
  ['kuliner', 'Kuliner'],
  ['oleh_oleh', 'Oleh-oleh'],
  ['transport', 'Transport'],
]

function formatRupiah(value) {
  return `Rp${Number(value || 0).toLocaleString('id-ID')}`
}

function App() {
  const [authMode, setAuthMode] = useState('login')
  const [authForm, setAuthForm] = useState({
    username: 'jogja_explorer',
    email: '',
    password: '',
  })
  const [token, setToken] = useState('')
  const [authMessage, setAuthMessage] = useState('')

  const [form, setForm] = useState({
    destination: 'Yogyakarta',
    days: 2,
    people: 2,
    budget: 1000000,
    interests: 'pantai, kuliner, oleh oleh',
    allocation_mode: 'default',
    transport_mode: 'motor_pribadi',
  })
  const [allocation, setAllocation] = useState(defaultAllocation)
  const [budgetPlan, setBudgetPlan] = useState(null)
  const [plannedSignature, setPlannedSignature] = useState('')
  const [itinerary, setItinerary] = useState(null)
  const [message, setMessage] = useState('')

  const totalPercentage = useMemo(
    () => Object.values(allocation).reduce((total, value) => total + Number(value || 0), 0),
    [allocation],
  )
  const allocationValid = form.allocation_mode === 'default' || totalPercentage === 100
  const canPlanBudget = token && allocationValid

  const requestBody = {
    destination: form.destination,
    days: Number(form.days),
    people: Number(form.people),
    budget: Number(form.budget),
    interests: form.interests
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean),
    allocation_mode: form.allocation_mode,
    custom_allocation: form.allocation_mode === 'custom' ? allocation : null,
    transport_mode: form.transport_mode,
  }
  const requestSignature = JSON.stringify(requestBody)
  const canGenerateItinerary = Boolean(token && budgetPlan && plannedSignature === requestSignature)

  async function submitAuth(event) {
    event.preventDefault()
    setAuthMessage('')

    const path = authMode === 'login' ? '/auth/login' : '/auth/register'
    const payload =
      authMode === 'login'
        ? { email: authForm.email, password: authForm.password }
        : authForm

    try {
      const response = await fetch(`${API_BASE_URL}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Authentication failed')
      }

      if (authMode === 'register') {
        setAuthMessage('Register berhasil. Silakan login.')
        setAuthMode('login')
        return
      }

      setToken(data.access_token)
      setAuthMessage('Login berhasil. Budget Planner sudah aktif.')
    } catch (error) {
      setAuthMessage(error.message)
    }
  }

  async function postAuthenticated(path, body) {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
    })
    const data = await response.json()

    if (!response.ok) {
      throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed')
    }

    return data
  }

  async function generateBudgetPlan() {
    setMessage('')
    setItinerary(null)

    try {
      const data = await postAuthenticated('/budget/plan', requestBody)
      setBudgetPlan(data)
      setPlannedSignature(requestSignature)
      setMessage('Budget planner berhasil. Itinerary sekarang bisa dibuat.')
    } catch (error) {
      setBudgetPlan(null)
      setMessage(error.message)
    }
  }

  async function generateItinerary() {
    setMessage('')

    try {
      const data = await postAuthenticated('/itinerary/generate', requestBody)
      setItinerary(data)
      setMessage('Itinerary berhasil dibuat dan disimpan.')
    } catch (error) {
      setMessage(error.message)
    }
  }

  return (
    <main className="app-shell">
      <section className="page-header">
        <p className="eyebrow">Smart Travel Planning System</p>
        <h1>Budget Planner dan Itinerary Generator</h1>
        <p>
          Alur sistem dibuat bertahap: login, rencanakan budget, validasi
          allocation, lalu generate itinerary.
        </p>
      </section>

      <section className="panel auth-panel">
        <div>
          <h2>Login</h2>
          <p>JWT digunakan agar budget dan itinerary terhubung ke user.</p>
        </div>
        <form onSubmit={submitAuth} className="form-grid">
          <div className="segmented">
            <button
              type="button"
              className={authMode === 'login' ? 'active' : ''}
              onClick={() => setAuthMode('login')}
            >
              Login
            </button>
            <button
              type="button"
              className={authMode === 'register' ? 'active' : ''}
              onClick={() => setAuthMode('register')}
            >
              Register
            </button>
          </div>

          {authMode === 'register' && (
            <label>
              Username
              <input
                value={authForm.username}
                onChange={(event) =>
                  setAuthForm({ ...authForm, username: event.target.value })
                }
              />
            </label>
          )}

          <label>
            Email
            <input
              type="email"
              value={authForm.email}
              onChange={(event) => setAuthForm({ ...authForm, email: event.target.value })}
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={authForm.password}
              onChange={(event) =>
                setAuthForm({ ...authForm, password: event.target.value })
              }
            />
          </label>
          <button type="submit">Submit</button>
        </form>
        {authMessage && <p className="status">{authMessage}</p>}
      </section>

      <section className="workspace">
        <div className="panel">
          <h2>Budget Planner</h2>
          <div className="form-grid">
            <label>
              Destination
              <input
                value={form.destination}
                onChange={(event) => setForm({ ...form, destination: event.target.value })}
              />
            </label>
            <label>
              Days
              <input
                type="number"
                min="1"
                value={form.days}
                onChange={(event) => setForm({ ...form, days: event.target.value })}
              />
            </label>
            <label>
              People
              <input
                type="number"
                min="1"
                value={form.people}
                onChange={(event) => setForm({ ...form, people: event.target.value })}
              />
            </label>
            <label>
              Budget
              <input
                type="number"
                min="1"
                value={form.budget}
                onChange={(event) => setForm({ ...form, budget: event.target.value })}
              />
            </label>
            <label>
              Interests
              <input
                value={form.interests}
                onChange={(event) => setForm({ ...form, interests: event.target.value })}
              />
            </label>
            <label>
              Transport
              <select
                value={form.transport_mode}
                onChange={(event) =>
                  setForm({ ...form, transport_mode: event.target.value })
                }
              >
                <option value="motor_pribadi">Motor pribadi</option>
                <option value="mobil_pribadi">Mobil pribadi</option>
                <option value="ojol">Ojol</option>
              </select>
            </label>
          </div>

          <div className="allocation-header">
            <h3>Allocation Mode</h3>
            <div className="segmented">
              <button
                type="button"
                className={form.allocation_mode === 'default' ? 'active' : ''}
                onClick={() => {
                  setForm({ ...form, allocation_mode: 'default' })
                  setAllocation(defaultAllocation)
                }}
              >
                Default
              </button>
              <button
                type="button"
                className={form.allocation_mode === 'custom' ? 'active' : ''}
                onClick={() => setForm({ ...form, allocation_mode: 'custom' })}
              >
                Custom
              </button>
            </div>
          </div>

          {form.allocation_mode === 'custom' && (
            <div className="allocation-grid">
              {categories.map(([key, label]) => (
                <label key={key}>
                  {label}
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={allocation[key]}
                    onChange={(event) =>
                      setAllocation({ ...allocation, [key]: Number(event.target.value) })
                    }
                  />
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={allocation[key]}
                    onChange={(event) =>
                      setAllocation({ ...allocation, [key]: Number(event.target.value) })
                    }
                  />
                </label>
              ))}
            </div>
          )}

          <div className={allocationValid ? 'percentage ok' : 'percentage warning'}>
            Total allocation: {totalPercentage}%
          </div>

          <div className="actions">
            <button type="button" onClick={generateBudgetPlan} disabled={!canPlanBudget}>
              Generate Budget Plan
            </button>
            <button
              type="button"
              onClick={generateItinerary}
              disabled={!canGenerateItinerary}
            >
              Generate Itinerary
            </button>
          </div>
          {message && <p className="status">{message}</p>}
        </div>

        <div className="panel output-panel">
          <h2>Budget Result</h2>
          {budgetPlan ? (
            <div className="result-list">
              <p>Total budget: {formatRupiah(budgetPlan.budget_total)}</p>
              <p>Budget per day: {formatRupiah(budgetPlan.budget_per_day)}</p>
              <p>Budget per person: {formatRupiah(budgetPlan.budget_per_person)}</p>
              <p>Transport estimate: {formatRupiah(budgetPlan.transport_estimate)}</p>
              {categories.map(([key, label]) => (
                <p key={key}>
                  {label}: {formatRupiah(budgetPlan.allocation[key])}
                </p>
              ))}
            </div>
          ) : (
            <p>Budget plan belum dibuat.</p>
          )}
        </div>
      </section>

      {itinerary && (
        <section className="panel itinerary-panel">
          <h2>Generated Itinerary</h2>
          <div className="days-grid">
            {itinerary.days.map((day) => (
              <article key={day.day}>
                <h3>Day {day.day}</h3>
                <p>Cost: {formatRupiah(day.day_cost)}</p>
                <ul>
                  {day.places.map((place) => (
                    <li key={`${day.day}-${place.name}`}>
                      <strong>{place.type}</strong> {place.name}
                      <span>{formatRupiah(place.price_estimate)}</span>
                    </li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </section>
      )}
    </main>
  )
}

export default App
