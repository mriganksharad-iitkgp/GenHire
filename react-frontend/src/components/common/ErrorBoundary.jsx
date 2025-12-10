import React from 'react';
import styles from './ErrorBoundary.module.css';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    // Log error to console in development
    if (process.env.NODE_ENV === 'development') {
      console.error('Error caught by boundary:', error, errorInfo);
    }
    
    // You can also log to an error reporting service here
    this.setState({
      error,
      errorInfo
    });
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null
    });
  };

  render() {
    if (this.state.hasError) {
      const { fallback } = this.props;
      
      // Use custom fallback if provided
      if (fallback) {
        return typeof fallback === 'function'
          ? fallback(this.state.error, this.handleReset)
          : fallback;
      }

      // Default error UI
      return (
        <div className={styles.container}>
          <div className={styles.content}>
            <div className={styles.iconWrapper}>
              <i className="fa fa-exclamation-triangle" aria-hidden="true"></i>
            </div>
            
            <h2 className={styles.title}>Oops! Something went wrong</h2>
            
            <p className={styles.message}>
              We encountered an unexpected error. Don't worry, your data is safe.
            </p>

            {process.env.NODE_ENV === 'development' && this.state.error && (
              <details className={styles.errorDetails}>
                <summary>Error Details (Development Only)</summary>
                <pre className={styles.errorStack}>
                  {this.state.error.toString()}
                  {this.state.errorInfo && this.state.errorInfo.componentStack}
                </pre>
              </details>
            )}

            <div className={styles.actions}>
              <button 
                className={styles.primaryButton}
                onClick={this.handleReset}
              >
                <i className="fa fa-refresh"></i>
                Try Again
              </button>
              
              <button 
                className={styles.secondaryButton}
                onClick={() => window.location.href = '/'}
              >
                <i className="fa fa-home"></i>
                Go Home
              </button>
            </div>

            <p className={styles.helpText}>
              If this problem persists, please contact support or try refreshing the page.
            </p>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

// Functional error fallback component
export const ErrorFallback = ({ error, resetError }) => (
  <div className={styles.container}>
    <div className={styles.content}>
      <div className={styles.iconWrapper}>
        <i className="fa fa-exclamation-circle" aria-hidden="true"></i>
      </div>
      
      <h2 className={styles.title}>Error</h2>
      
      <p className={styles.message}>
        {error?.message || 'An unexpected error occurred'}
      </p>

      <button className={styles.primaryButton} onClick={resetError}>
        <i className="fa fa-refresh"></i>
        Try Again
      </button>
    </div>
  </div>
);

export default ErrorBoundary;
