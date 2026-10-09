import React from 'react';
import styles from './JDDetailsModal.module.css';

const JDDetailsModal = ({ isOpen, onClose, session, getRoleName, getRoleIcon }) => {
  if (!isOpen || !session) return null;

  const roles = [
    { id: 'software-engineer', name: 'Software Engineer', icon: 'fa-code', 
      description: 'Design, develop, and maintain high-quality software applications using modern technologies and best practices', 
      responsibilities: 'Design and architect scalable software solutions, Write clean and maintainable code following industry best practices, Implement automated testing and continuous integration, Collaborate with cross-functional teams including designers and product managers, Participate in code reviews and mentor junior developers, Debug and optimize application performance, Maintain technical documentation and system architecture diagrams',
      requirements: 'Bachelor\'s or Master\'s degree in Computer Science or related field, 3+ years of hands-on software development experience, Strong proficiency in programming languages (Java Python JavaScript TypeScript), Deep understanding of data structures algorithms and design patterns, Experience with modern web frameworks (React Angular Vue Node.js), Knowledge of databases (SQL and NoSQL) and RESTful APIs, Familiarity with version control systems (Git) and CI/CD pipelines, Excellent problem-solving and debugging skills, Strong communication and teamwork abilities'
    },
    { id: 'data-scientist', name: 'Data Scientist', icon: 'fa-line-chart', 
      description: 'Leverage advanced analytics and machine learning to extract meaningful insights from complex datasets and drive data-informed decision making',
      responsibilities: 'Collect clean and preprocess large-scale datasets from multiple sources, Perform exploratory data analysis and feature engineering, Build deploy and monitor machine learning models in production, Create compelling data visualizations and interactive dashboards, Conduct statistical analysis and A/B testing, Collaborate with business stakeholders to translate requirements into analytical solutions, Communicate complex findings to non-technical audiences, Stay updated with latest ML/AI techniques and best practices',
      requirements: 'Master\'s or PhD in Data Science Statistics Computer Science or quantitative field, 3-5 years of hands-on experience in data science and machine learning, Expert-level Python/R programming with libraries like pandas numpy scikit-learn, Deep knowledge of ML algorithms (supervised unsupervised deep learning), Proficiency in SQL and working with large databases, Experience with ML frameworks (TensorFlow PyTorch Keras), Strong understanding of statistical concepts and experimental design, Experience with data visualization tools (Tableau PowerBI Matplotlib Seaborn), Cloud platform experience (AWS Azure GCP), Excellent analytical and problem-solving skills'
    },
    { id: 'product-manager', name: 'Product Manager', icon: 'fa-tasks', 
      description: 'Define and execute product strategy from conception to launch while balancing user needs business goals and technical constraints',
      responsibilities: 'Define comprehensive product vision strategy and long-term roadmap, Conduct extensive market research competitive analysis and user research, Gather and prioritize product requirements from multiple stakeholders, Create detailed product specifications wireframes and user stories, Work closely with engineering design and marketing teams throughout development lifecycle, Make data-driven decisions using analytics and user feedback, Manage product launches and go-to-market strategies, Monitor product metrics KPIs and iterate based on performance, Lead product planning meetings and stakeholder presentations',
      requirements: 'Bachelor\'s degree in Business Engineering Computer Science or related field MBA preferred, 5-7 years of product management experience in tech industry, Proven track record of successfully launching and scaling products, Strong understanding of Agile/Scrum methodologies, Experience with product analytics tools (Google Analytics Mixpanel Amplitude), Proficiency in product management tools (JIRA Asana ProductBoard), Excellent analytical skills with ability to make data-driven decisions, Outstanding communication presentation and stakeholder management skills, Strong leadership abilities with cross-functional team collaboration, Technical aptitude to work effectively with engineering teams'
    },
    { id: 'business-analyst', name: 'Business Analyst', icon: 'fa-briefcase', 
      description: 'Bridge the gap between business needs and technical solutions through comprehensive analysis process improvement and stakeholder collaboration',
      responsibilities: 'Gather document and analyze business requirements from diverse stakeholders, Conduct process mapping and identify workflow optimization opportunities, Create detailed functional specifications user stories and acceptance criteria, Facilitate requirements workshops and stakeholder interviews, Develop business cases cost-benefit analyses and ROI calculations, Collaborate with development teams to ensure requirements are properly implemented, Perform user acceptance testing and validate solutions meet business needs, Create comprehensive documentation including process flows and data models, Monitor and report on project progress and KPIs',
      requirements: 'Bachelor\'s degree in Business Administration Information Technology or related field, 3-5 years of business analysis experience preferably in agile environments, Strong proficiency in requirements elicitation and documentation techniques, Experience with business process modeling tools (Visio Lucidchart BPMN), Knowledge of SQL and database concepts for data analysis, Familiarity with project management methodologies (Agile Scrum Waterfall), Proficiency in tools like JIRA Confluence Excel, Excellent analytical and critical thinking skills, Strong communication and stakeholder management abilities, Certification in business analysis (CBAP PMI-PBA) is a plus'
    },
    { id: 'fullstack-developer', name: 'Full Stack Developer', icon: 'fa-laptop', 
      description: 'Build and maintain complete web applications from frontend to backend database and deployment using modern full-stack technologies',
      responsibilities: 'Develop responsive and intuitive user interfaces using modern frontend frameworks, Build robust and scalable backend services and APIs, Design and implement efficient database schemas and queries, Integrate third-party services and APIs, Implement authentication authorization and security best practices, Write comprehensive unit integration and end-to-end tests, Optimize application performance and loading times, Deploy and maintain applications on cloud platforms, Collaborate with designers product managers and other developers, Participate in code reviews and technical discussions',
      requirements: 'Bachelor\'s degree in Computer Science or equivalent experience, 3-4 years of full-stack development experience, Strong proficiency in frontend technologies (HTML CSS JavaScript TypeScript), Expert knowledge of modern frontend frameworks (React Angular or Vue.js), Solid backend development skills (Node.js Python Java or C#), Experience building RESTful APIs and working with microservices, Proficiency in both SQL (PostgreSQL MySQL) and NoSQL (MongoDB Redis) databases, Knowledge of version control (Git) and CI/CD practices, Familiarity with cloud platforms (AWS Azure or Google Cloud), Understanding of containerization (Docker) and orchestration (Kubernetes), Strong problem-solving and debugging skills, Excellent communication and teamwork abilities'
    },
    { id: 'devops-engineer', name: 'DevOps Engineer', icon: 'fa-server', 
      description: 'Design implement and maintain automated infrastructure CI/CD pipelines and cloud-based systems to enable rapid and reliable software delivery',
      responsibilities: 'Design build and maintain robust CI/CD pipelines for automated testing and deployment, Manage and optimize cloud infrastructure across multiple environments, Implement infrastructure as code using tools like Terraform Ansible or CloudFormation, Configure and manage containerized applications using Docker and Kubernetes, Set up comprehensive monitoring logging and alerting systems, Automate routine operational tasks and processes, Ensure high availability scalability and disaster recovery capabilities, Implement security best practices and compliance requirements, Optimize infrastructure costs and resource utilization, Collaborate with development teams to improve deployment processes and system reliability, Respond to and resolve production incidents and outages',
      requirements: 'Bachelor\'s degree in Computer Science Information Technology or related field, 3-5 years of DevOps or Site Reliability Engineering experience, Extensive experience with cloud platforms (AWS Azure or Google Cloud Platform), Strong proficiency in containerization technologies (Docker Kubernetes Helm), Expert knowledge of infrastructure as code tools (Terraform Ansible Puppet Chef), Experience with CI/CD tools (Jenkins GitLab CI GitHub Actions CircleCI), Solid scripting skills (Python Bash PowerShell), Deep understanding of Linux/Unix system administration, Knowledge of monitoring and logging tools (Prometheus Grafana ELK Stack Datadog), Experience with configuration management and orchestration, Understanding of networking security and compliance concepts, Strong troubleshooting and problem-solving abilities, Excellent collaboration and communication skills'
    }
  ];

  const roleInfo = roles.find(r => r.id === session.role) || {};

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <h2>
            <i className={`fa ${getRoleIcon?.(session.role) || roleInfo.icon || 'fa-briefcase'}`}></i>
            Job Description Details
          </h2>
          <button className={styles.closeButton} onClick={onClose} aria-label="Close dialog">
            <i className="fa fa-times"></i>
          </button>
        </div>

        <div className={styles.modalBody}>
          {/* Role Information */}
          <div className={styles.section}>
            <h3><i className="fa fa-briefcase"></i> Role Overview</h3>
            <div className={styles.roleCard}>
              <div className={styles.roleHeader}>
                <div className={styles.roleIcon}>
                  <i className={`fa ${getRoleIcon?.(session.role) || roleInfo.icon || 'fa-briefcase'}`}></i>
                </div>
                <div className={styles.roleInfo}>
                  <h4>{getRoleName?.(session.role) || roleInfo.name || session.role}</h4>
                  {roleInfo.description && (
                    <p className={styles.roleDescription}>{roleInfo.description}</p>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Key Responsibilities */}
          {roleInfo.responsibilities && (
            <div className={styles.section}>
              <h3><i className="fa fa-tasks"></i> Key Responsibilities</h3>
              <div className={styles.card}>
                <ul className={styles.bulletList}>
                  {roleInfo.responsibilities.split(', ').map((item, index) => (
                    <li key={index}>
                      <i className="fa fa-check-circle" style={{ color: '#10b981', marginRight: '8px' }}></i>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Requirements */}
          {roleInfo.requirements && (
            <div className={styles.section}>
              <h3><i className="fa fa-list-ul"></i> Requirements & Qualifications</h3>
              <div className={styles.card}>
                <ul className={styles.bulletList}>
                  {roleInfo.requirements.split(', ').map((item, index) => (
                    <li key={index}>
                      <i className="fa fa-star" style={{ color: '#f59e0b', marginRight: '8px' }}></i>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Session Information */}
          <div className={styles.section}>
            <h3><i className="fa fa-info-circle"></i> Practice Session Information</h3>
            <div className={styles.infoGrid}>
              <div className={styles.infoCard}>
                <div className={styles.infoIcon}>
                  <i className="fa fa-hashtag"></i>
                </div>
                <div className={styles.infoContent}>
                  <span className={styles.infoLabel}>Session ID</span>
                  <span className={styles.infoValue}>{session.session_id}</span>
                </div>
              </div>

              <div className={styles.infoCard}>
                <div className={styles.infoIcon}>
                  <i className="fa fa-calendar"></i>
                </div>
                <div className={styles.infoContent}>
                  <span className={styles.infoLabel}>Practice Date</span>
                  <span className={styles.infoValue}>
                    {new Date(session.created_at).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata',
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric'
                    })}
                  </span>
                </div>
              </div>

              <div className={styles.infoCard}>
                <div className={styles.infoIcon}>
                  <i className="fa fa-map-marker"></i>
                </div>
                <div className={styles.infoContent}>
                  <span className={styles.infoLabel}>Mode</span>
                  <span className={styles.infoValue}>Practice Interview</span>
                </div>
              </div>

              <div className={styles.infoCard}>
                <div className={styles.infoIcon}>
                  <i className="fa fa-clock-o"></i>
                </div>
                <div className={styles.infoContent}>
                  <span className={styles.infoLabel}>Status</span>
                  <span className={`${styles.infoValue} ${styles.statusBadge}`}>
                    {session.status === 'completed' || session.status === 'ended' ? 'Completed' : 'In Progress'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className={styles.modalFooter}>
          <button className={styles.closeBtn} onClick={onClose}>
            <i className="fa fa-times"></i> Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default JDDetailsModal;
