import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import DiseaseDataByType from './components/DiseaseDataByType';
import AdminLayout from './components/admin/AdminLayout';
import Login from './components/admin/Login';
import ProtectedRoute from './components/admin/ProtectedRoute';
import Dashboard from './components/admin/Dashboard';
import Sources from './components/admin/Sources';
import Diseases from './components/admin/Diseases';
import Jobs from './components/admin/Jobs';
import Schedules from './components/admin/Schedules';
import './App.css';

function App() {
  return (
    <Router>
      <div className="App">
        <Routes>
          {/* Public routes */}
          <Route path="/" element={<DiseaseDataByType />} />
          
          {/* Admin routes */}
          <Route path="/admin/login" element={<Login />} />
          <Route
            path="/admin"
            element={
              <ProtectedRoute>
                <AdminLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/admin/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="sources" element={<Sources />} />
            <Route path="diseases" element={<Diseases />} />
            <Route path="jobs" element={<Jobs />} />
            <Route path="schedules" element={<Schedules />} />
          </Route>
        </Routes>
      </div>
    </Router>
  );
}

export default App;
