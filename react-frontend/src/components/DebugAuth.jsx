import React, { useState } from 'react';

const DebugAuth = () => {
    const [debugInfo, setDebugInfo] = useState({});

    const checkAuth = () => {
        const token = localStorage.getItem(process.env.REACT_APP_TOKEN_KEY);
        const user = localStorage.getItem(process.env.REACT_APP_USER_KEY);
        
        setDebugInfo({
            tokenKey: process.env.REACT_APP_TOKEN_KEY,
            userKey: process.env.REACT_APP_USER_KEY,
            token: token,
            user: user ? JSON.parse(user) : null,
            allLocalStorage: Object.keys(localStorage).reduce((acc, key) => {
                acc[key] = localStorage.getItem(key);
                return acc;
            }, {})
        });
    };

    const clearAuth = () => {
        localStorage.removeItem(process.env.REACT_APP_TOKEN_KEY);
        localStorage.removeItem(process.env.REACT_APP_USER_KEY);
        checkAuth();
    };

    return (
        <div style={{ padding: '20px', border: '1px solid #ccc', margin: '10px' }}>
            <h3>Auth Debug Panel</h3>
            <button onClick={checkAuth}>Check Auth Status</button>
            <button onClick={clearAuth} style={{ marginLeft: '10px' }}>Clear Auth</button>
            
            {Object.keys(debugInfo).length > 0 && (
                <pre style={{ background: '#f5f5f5', padding: '10px', marginTop: '10px' }}>
                    {JSON.stringify(debugInfo, null, 2)}
                </pre>
            )}
        </div>
    );
};

export default DebugAuth;