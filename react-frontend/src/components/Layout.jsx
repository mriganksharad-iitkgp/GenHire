import React, {useState, useEffect} from "react";
import { Navigate, useNavigate } from "react-router-dom";
import Navbar from "./Navbar";
import styles from "./Layout.module.css";
import axios from "axios";

const Layout = ({ children }) => {
    const navigate = useNavigate();
    const [isAuthenticated, setIsAuthenticated] = useState(null);

    useEffect(() => {
        const verifyAuth = async () => {
            const token = localStorage.getItem('token');
            
            if (!token) {
                setIsAuthenticated(false);
                return;
            }

            try {
                // Verify token with backend
                const response = await axios.get('http://127.0.0.1:5000/api/me', {
                    headers: {
                        'Authorization': token
                    }
                });
                
                if (response.data) {
                    setIsAuthenticated(true);
                } else {
                    localStorage.removeItem('token');
                    localStorage.removeItem('user');
                    localStorage.removeItem('isAuthenticated');
                    setIsAuthenticated(false);
                }
            } catch (error) {
                localStorage.removeItem('token');
                localStorage.removeItem('user');
                localStorage.removeItem('isAuthenticated');
                setIsAuthenticated(false);
            }
        };

        verifyAuth();
    }, [navigate]);

    if (isAuthenticated === null) {
        return <div>Loading...</div>; // Or a loading spinner
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    return (
        <div className={styles.layoutContainer}>
            <Navbar />
            <main className={styles.mainContent}>{children}</main>
        </div>
    );
};

export default Layout;
