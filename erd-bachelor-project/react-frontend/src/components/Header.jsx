import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';

function Header() {
  const [theme, setTheme] = useState('light');
  const location = useLocation();

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const initialTheme = savedTheme || (prefersDark ? 'dark' : 'light');
    setTheme(initialTheme);
    document.body.dataset.theme = initialTheme;
  }, []);

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    document.body.dataset.theme = newTheme;
    localStorage.setItem('theme', newTheme);
  };

  const getDescription = () => {
    if (location.pathname === '/') return 'Welcome to the ERD analysis and grading platform';
    if (location.pathname === '/visualizer') return 'Upload student & TA SVG files to compare and automatically grade ERD submissions';
    if (location.pathname === '/schema-grader') return 'Grade student ERDs using structured evaluation rubrics';
    return 'ERD analysis and grading platform';
  };

  return (
    <div className="header">
      <div>
        <h1>ERD Visualizer & AI Grader</h1>
        <p>{getDescription()}</p>
        <div style={{ marginTop: '15px', display: 'flex', gap: '15px' }}>
          <Link to="/" className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}>
            Home
          </Link>
          <Link to="/visualizer" className={`nav-link ${location.pathname === '/visualizer' ? 'active' : ''}`}>
            AI Grader
          </Link>
          <Link to="/schema-grader" className={`nav-link ${location.pathname === '/schema-grader' ? 'active' : ''}`}>
            Schema Grader
          </Link>
        </div>
      </div>
      <div className="theme-switch-wrapper">
        <span className="theme-switch-label">Mode</span>
        <input
          type="checkbox"
          className="theme-checkbox"
          checked={theme === 'dark'}
          onChange={toggleTheme}
        />
      </div>
    </div>
  );
}

export default Header;
