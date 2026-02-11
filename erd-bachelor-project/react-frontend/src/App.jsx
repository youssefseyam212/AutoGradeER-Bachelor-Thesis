import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Header from './components/Header';
import Home from './pages/Home';
import Visualizer from './pages/Visualizer';
import SchemaGrader from './pages/SchemaGrader';
import './styles/App.css';

function App() {
  return (
    <Router>
      <div className="container page-wrapper">
        <Header />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/visualizer" element={<Visualizer />} />
          <Route path="/schema-grader" element={<SchemaGrader />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
