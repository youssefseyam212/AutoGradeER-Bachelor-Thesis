import { Link } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faChartLine, faRobot, faBullseye } from '@fortawesome/free-solid-svg-icons';

function Home() {
  return (
    <div className="content">
      <div className="landing-container">
        <h1 className="landing-title">ERD Visualizer & AI Grader</h1>
        <p className="landing-description">
          Transform your Entity-Relationship Diagrams into interactive visualizations and leverage AI-powered grading to provide instant feedback on student submissions.
        </p>

        <div className="feature-grid">
          <div className="feature-card">
            <div className="feature-icon">
              <FontAwesomeIcon icon={faChartLine} />
            </div>
            <h3 className="feature-title">Visualize ERDs</h3>
            <p className="feature-description">
              Upload SVG, GraphML, or XML files and convert them into structured, interactive diagrams with entities, relationships, and inheritance hierarchies.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon">
              <FontAwesomeIcon icon={faRobot} />
            </div>
            <h3 className="feature-title">AI-Powered Grading</h3>
            <p className="feature-description">
              Compare student submissions against teaching assistant solutions and receive detailed AI-generated feedback and grades.
            </p>
          </div>

          <div className="feature-card">
            <div className="feature-icon">
              <FontAwesomeIcon icon={faBullseye} />
            </div>
            <h3 className="feature-title">Detailed Analysis</h3>
            <p className="feature-description">
              Get comprehensive breakdowns of entities, relationships, cardinalities, and inheritance patterns with instant statistics.
            </p>
          </div>
        </div>

        <Link to="/visualizer" className="g-button g-button-contained cta-button">
          Get Started →
        </Link>
      </div>
    </div>
  );
}

export default Home;
