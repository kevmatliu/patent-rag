import React, { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error in application:", error, errorInfo);
  }

  private handleRetry = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="workspace-inline-state workspace-inline-state-error" style={{ margin: "20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <h2 style={{ fontSize: "1.2rem", margin: "0 0 8px 0", color: "#8b0000" }}>
                Something went wrong
              </h2>
              <p style={{ margin: "0 0 16px 0", color: "#607784" }}>
                The application encountered an unexpected error. This often happens if a 3rd-party component
                like the Ketcher editor fails to initialize correctly during navigation.
              </p>
              {this.state.error && (
                <pre style={{ 
                  margin: "0 0 16px 0", 
                  padding: "12px", 
                  background: "#fff5f5", 
                  borderRadius: "8px", 
                  fontSize: "0.85rem",
                  overflowX: "auto",
                  border: "1px solid #ffcccc"
                }}>
                  {this.state.error.message}
                </pre>
              )}
              <button 
                className="primary-button small" 
                onClick={this.handleRetry}
                type="button"
              >
                Reload Application
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
