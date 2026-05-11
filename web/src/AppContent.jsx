import React, { useState, useEffect } from 'react';
import { Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import SuggestionsPage from './components/SuggestionsPage';
import ChatPage from './components/ChatPage';

const MOBILE_BREAKPOINT = 768; // px

const AppContent = ({ suggestionsData, activeChats, setActiveChats }) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(
    typeof window !== 'undefined' ? window.innerWidth >= MOBILE_BREAKPOINT : true
  );
  const [isMobile, setIsMobile] = useState(
    typeof window !== 'undefined' ? window.innerWidth < MOBILE_BREAKPOINT : false
  );

  useEffect(() => {
    const handleResize = () => {
      const mobileNow = window.innerWidth < MOBILE_BREAKPOINT;
      setIsMobile(mobileNow);

      setIsSidebarOpen((prev) => {
        if (mobileNow && prev) return false;   // collapse
        if (!mobileNow && !prev) return true;  // expand
        return prev;
      });
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const toggleSidebar = () => setIsSidebarOpen((prev) => !prev);

  const handleOpenChat = (suggestion) => {
    setActiveChats((prev) => {
      const alreadyActive = prev.some((s) => s.id === suggestion.id);
      return alreadyActive ? prev : [...prev, suggestion];
    });
  };

  return (
    <div
      className="app-container"
      style={{ display: 'flex', position: 'relative', height: '500px' }}
    >
      {isSidebarOpen && (
        <Navbar
          activeChats={activeChats}
          isMobile={isMobile}
          onClose={toggleSidebar}
        />
      )}

      {/* Hamburger – absolute inside this container, not the whole page */}
      {!isSidebarOpen && isMobile && (
        <button
          aria-label="Open sidebar"
          onClick={toggleSidebar}
          style={{
            position: 'absolute',
            top: 10,
            left: 10,
            zIndex: 20,
            background: 'none',
            border: 'none',
            fontSize: '1.8rem',
            color: '#d6ceba',
            cursor: 'pointer',
          }}
        >
          &#9776;
        </button>
      )}

      <div className="main-content" style={{ flex: 1 }}>
        <Routes>
          <Route
            path="/"
            element={<SuggestionsPage suggestionsData={suggestionsData} />}
          />
          <Route
            path="/chat/:id"
            element={<ChatPage onOpenChat={handleOpenChat} />}
          />
        </Routes>
      </div>
    </div>
  );
};

export default AppContent;
