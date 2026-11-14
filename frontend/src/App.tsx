import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { TopNav } from './components/TopNav';
import { HomePage } from './pages/HomePage';
import { ExplorePage } from './pages/ExplorePage';
import { RegionPage } from './pages/RegionPage';
import { TrendsPage } from './pages/TrendsPage';
import { ChangesPage } from './pages/ChangesPage';
import { SignificancePage } from './pages/SignificancePage';

export const AppRoutes: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col bg-background text-slate-100 selection:bg-accent-blue/30 selection:text-cyan-200">
      <TopNav />
      <div className="flex-1">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/explore" element={<ExplorePage />} />
          <Route path="/region" element={<RegionPage />} />
          <Route path="/trends" element={<TrendsPage />} />
          <Route path="/changes" element={<ChangesPage />} />
          <Route path="/significance" element={<SignificancePage />} />
          {/* Fallback route */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
};

export default App;
