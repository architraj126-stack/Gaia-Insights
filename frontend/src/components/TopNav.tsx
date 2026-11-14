import React, { useState } from 'react';
import { NavLink, Link, useNavigate, useLocation } from 'react-router-dom';
import { Globe2, Menu, X, ArrowRight } from 'lucide-react';
import { useSession } from '../store/session';

export const TopNav: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const sessionId = useSession((state) => state.sessionId);

  const handleNavClick = (anchorId: string) => {
    setMobileMenuOpen(false);
    if (location.pathname === '/') {
      const el = document.getElementById(anchorId);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth' });
        return;
      }
    }
    navigate(`/#${anchorId}`);
  };

  const isWorkflowRoute = ['/explore', '/region', '/trends', '/changes', '/significance'].includes(location.pathname);

  return (
    <header className="sticky top-0 z-50 bg-background-elevated/95 backdrop-blur-md border-b border-border-subtle shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo / Branding */}
          <Link
            to="/"
            className="flex items-center gap-2.5 text-white font-semibold text-lg tracking-tight hover:opacity-90 transition-opacity"
          >
            <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-accent-blue to-accent-cyan flex items-center justify-center shadow-lg shadow-accent-blue/20">
              <Globe2 className="w-5 h-5 text-navy-950" />
            </div>
            <div className="flex flex-col">
              <span className="leading-tight text-slate-100 font-bold">Earth Science Explorer</span>
              <span className="text-[10px] text-cyan-400 font-mono tracking-wider uppercase">Historical Data Analysis</span>
            </div>
          </Link>

          {/* Desktop Navigation Links (SPEC 4.1) */}
          <nav className="hidden md:flex items-center space-x-1 lg:space-x-2">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  isActive
                    ? 'bg-accent-blue/15 text-cyan-300 border border-accent-blue/30'
                    : 'text-slate-300 hover:text-white hover:bg-navy-800'
                }`
              }
            >
              Home
            </NavLink>

            <NavLink
              to="/explore"
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  isActive
                    ? 'bg-accent-blue/15 text-cyan-300 border border-accent-blue/30'
                    : 'text-slate-300 hover:text-white hover:bg-navy-800'
                }`
              }
            >
              Explore
            </NavLink>

            <button
              type="button"
              onClick={() => handleNavClick('about')}
              className="px-3 py-1.5 rounded-md text-xs font-medium text-slate-300 hover:text-white hover:bg-navy-800 transition-colors cursor-pointer"
            >
              About
            </button>

            <button
              type="button"
              onClick={() => handleNavClick('data-sources')}
              className="px-3 py-1.5 rounded-md text-xs font-medium text-slate-300 hover:text-white hover:bg-navy-800 transition-colors cursor-pointer"
            >
              Data Sources
            </button>

            {/* Workflow Quick Links when in analysis workflow */}
            {isWorkflowRoute && (
              <div className="hidden lg:flex items-center pl-3 border-l border-border-subtle gap-1">
                <NavLink
                  to="/region"
                  className={({ isActive }) =>
                    `px-2 py-1 rounded text-[11px] font-medium transition-colors ${
                      isActive ? 'text-cyan-300 bg-navy-800' : 'text-slate-400 hover:text-slate-200'
                    }`
                  }
                >
                  Region
                </NavLink>
                <NavLink
                  to="/trends"
                  className={({ isActive }) =>
                    `px-2 py-1 rounded text-[11px] font-medium transition-colors ${
                      isActive ? 'text-cyan-300 bg-navy-800' : 'text-slate-400 hover:text-slate-200'
                    }`
                  }
                >
                  Trends
                </NavLink>
                <NavLink
                  to="/changes"
                  className={({ isActive }) =>
                    `px-2 py-1 rounded text-[11px] font-medium transition-colors ${
                      isActive ? 'text-cyan-300 bg-navy-800' : 'text-slate-400 hover:text-slate-200'
                    }`
                  }
                >
                  Changes
                </NavLink>
                <NavLink
                  to="/significance"
                  className={({ isActive }) =>
                    `px-2 py-1 rounded text-[11px] font-medium transition-colors ${
                      isActive ? 'text-cyan-300 bg-navy-800' : 'text-slate-400 hover:text-slate-200'
                    }`
                  }
                >
                  Reports
                </NavLink>
              </div>
            )}
          </nav>

          {/* Right Section: Session & Primary CTA (SPEC 4.1 "Get Started") */}
          <div className="hidden sm:flex items-center gap-3">
            <div className="text-[11px] font-mono bg-navy-800/80 border border-slate-700/60 rounded-md px-2.5 py-1 text-slate-400 hidden xl:block">
              <span className="text-slate-500">Session: </span>
              <span className="text-slate-200">{sessionId.slice(0, 14)}</span>
            </div>

            <Link
              to="/explore"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-gradient-to-r from-accent-blue to-accent-cyan text-navy-950 font-semibold text-xs hover:opacity-95 shadow-md shadow-accent-blue/20 transition-all"
            >
              <span>Get Started</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {/* Mobile menu button */}
          <div className="md:hidden flex items-center gap-2">
            <Link
              to="/explore"
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-gradient-to-r from-accent-blue to-accent-cyan text-navy-950 font-semibold text-xs"
            >
              <span>Explore</span>
            </Link>
            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-1.5 rounded-md text-slate-300 hover:text-white hover:bg-navy-800"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Mobile dropdown menu */}
        {mobileMenuOpen && (
          <div className="md:hidden py-3 border-t border-border-subtle space-y-1">
            <Link
              to="/"
              onClick={() => setMobileMenuOpen(false)}
              className="block px-3 py-2 rounded-md text-sm font-medium text-slate-200 hover:bg-navy-800"
            >
              Home
            </Link>
            <Link
              to="/explore"
              onClick={() => setMobileMenuOpen(false)}
              className="block px-3 py-2 rounded-md text-sm font-medium text-cyan-300 bg-accent-blue/10"
            >
              Explore Data (Page 1)
            </Link>
            <button
              type="button"
              onClick={() => handleNavClick('about')}
              className="w-full text-left px-3 py-2 rounded-md text-sm font-medium text-slate-200 hover:bg-navy-800"
            >
              About Project
            </button>
            <button
              type="button"
              onClick={() => handleNavClick('data-sources')}
              className="w-full text-left px-3 py-2 rounded-md text-sm font-medium text-slate-200 hover:bg-navy-800"
            >
              Data Sources & Metadata
            </button>
            <div className="pt-2 border-t border-border-subtle/60 grid grid-cols-2 gap-1 text-xs">
              <Link
                to="/region"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-1.5 rounded text-slate-400 hover:text-slate-200 hover:bg-navy-800"
              >
                2. Region
              </Link>
              <Link
                to="/trends"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-1.5 rounded text-slate-400 hover:text-slate-200 hover:bg-navy-800"
              >
                3. Trends
              </Link>
              <Link
                to="/changes"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-1.5 rounded text-slate-400 hover:text-slate-200 hover:bg-navy-800"
              >
                4. Changes
              </Link>
              <Link
                to="/significance"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-1.5 rounded text-slate-400 hover:text-slate-200 hover:bg-navy-800"
              >
                5. Reports
              </Link>
            </div>
          </div>
        )}
      </div>
    </header>
  );
};
