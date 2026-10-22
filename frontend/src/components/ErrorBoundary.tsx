import React from 'react';

interface ErrorBoundaryProps {
  /** Changing this value (for example the active module) clears a previous error. */
  resetKey?: string;
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
  resetKey?: string;
}

/**
 * Keeps a rendering failure in one module from blanking the whole application shell.
 */
export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null, resetKey: this.props.resetKey };

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { error };
  }

  // Navigating to another module (resetKey change) clears a previous error.
  static getDerivedStateFromProps(
    props: ErrorBoundaryProps,
    state: ErrorBoundaryState
  ): Partial<ErrorBoundaryState> | null {
    return props.resetKey !== state.resetKey ? { error: null, resetKey: props.resetKey } : null;
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('Module rendering failed:', error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="erp-alert alert-danger" role="alert" style={{ margin: '1.5rem' }}>
          <strong>This screen could not be displayed.</strong>
          <p>{this.state.error.message}</p>
          <button className="erp-btn btn-secondary" onClick={() => this.setState({ error: null })}>
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
