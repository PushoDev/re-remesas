import { NavLink, Outlet } from 'react-router-dom'

const tabClass = ({ isActive }: { isActive: boolean }) =>
  `border-b-2 px-1 pb-3 text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 ${
    isActive ? 'border-blue-700 text-blue-800' : 'border-transparent text-slate-500 hover:text-slate-800'
  }`

/** Frame of the administration area. More tabs (remittances, recharges...) will be added here. */
export default function AdminLayout() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Administración</h1>
        <nav aria-label="Administración" className="mt-4 flex gap-6 border-b border-slate-200">
          <NavLink to="/admin/exchange-rates" className={tabClass}>
            Tasas de cambio
          </NavLink>
        </nav>
      </div>
      <Outlet />
    </div>
  )
}
