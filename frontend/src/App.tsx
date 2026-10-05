import { Route, Routes } from 'react-router-dom'
import AdminRoute from './components/AdminRoute'
import ProtectedRoute from './components/ProtectedRoute'
import AdminLayout from './layouts/AdminLayout'
import AppLayout from './layouts/AppLayout'
import AdminOverviewPage from './pages/admin/AdminOverviewPage'
import AdminRechargesPage from './pages/admin/AdminRechargesPage'
import AdminRemittanceDetailPage from './pages/admin/AdminRemittanceDetailPage'
import AdminRemittancesPage from './pages/admin/AdminRemittancesPage'
import ExchangeRatesPage from './pages/admin/ExchangeRatesPage'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import MembershipPage from './pages/MembershipPage'
import MembershipResultPage from './pages/MembershipResultPage'
import MockCheckoutPage from './pages/MockCheckoutPage'
import ProfilePage from './pages/ProfilePage'
import RechargeDetailPage from './pages/RechargeDetailPage'
import RechargeListPage from './pages/RechargeListPage'
import RechargeNewPage from './pages/RechargeNewPage'
import RemittanceDetailPage from './pages/RemittanceDetailPage'
import RemittanceListPage from './pages/RemittanceListPage'
import RemittanceNewPage from './pages/RemittanceNewPage'
import RegisterPage from './pages/RegisterPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* Screens that need a session */}
      <Route element={<ProtectedRoute />}>
        {/* Simulated payment gateway page: full screen, outside the app frame */}
        <Route path="/pay/mock/:reference" element={<MockCheckoutPage />} />

        <Route element={<AppLayout />}>
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/remittances" element={<RemittanceListPage />} />
          <Route path="/remittances/new" element={<RemittanceNewPage />} />
          <Route path="/remittances/:trackingId" element={<RemittanceDetailPage />} />
          <Route path="/recharges" element={<RechargeListPage />} />
          <Route path="/recharges/new" element={<RechargeNewPage />} />
          <Route path="/recharges/:reference" element={<RechargeDetailPage />} />
          <Route path="/membership" element={<MembershipPage />} />
          <Route path="/membership/result" element={<MembershipResultPage />} />

          {/* Administrators only */}
          <Route element={<AdminRoute />}>
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<AdminOverviewPage />} />
              <Route path="remittances" element={<AdminRemittancesPage />} />
              <Route path="remittances/:trackingId" element={<AdminRemittanceDetailPage />} />
              <Route path="recharges" element={<AdminRechargesPage />} />
              <Route path="exchange-rates" element={<ExchangeRatesPage />} />
            </Route>
          </Route>
        </Route>
      </Route>
    </Routes>
  )
}

export default App
