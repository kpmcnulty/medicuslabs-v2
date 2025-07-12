import React from 'react';
import { Link, Outlet, useNavigate, useLocation } from 'react-router-dom';
import { adminApi } from '../../api/admin';
import './AdminLayout.css';

const AdminLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    adminApi.logout();
    navigate('/admin/login');
  };

  const isActive = (path: string) => {
    return location.pathname.startsWith(path) ? 'active' : '';
  };

  return (
    <div className="admin-layout">
      <header className="admin-header">
        <div className="admin-header-content">
          <h1>MedicusLabs Admin</h1>
          <button onClick={handleLogout} className="logout-button">
            Logout
          </button>
        </div>
      </header>

      <div className="admin-container">
        <nav className="admin-sidebar">
          <ul className="admin-nav">
            <li className={isActive('/admin/dashboard')}>
              <Link to="/admin/dashboard">Dashboard</Link>
            </li>
            <li className={isActive('/admin/sources')}>
              <Link to="/admin/sources">Sources</Link>
            </li>
            <li className={isActive('/admin/diseases')}>
              <Link to="/admin/diseases">Diseases</Link>
            </li>
            <li className={isActive('/admin/jobs')}>
              <Link to="/admin/jobs">Crawl Jobs</Link>
            </li>
            <li className={isActive('/admin/schedules')}>
              <Link to="/admin/schedules">Schedules</Link>
            </li>
          </ul>
        </nav>

        <main className="admin-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default AdminLayout;