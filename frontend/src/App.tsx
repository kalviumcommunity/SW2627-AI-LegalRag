import React, { useState } from 'react';
import { Sidebar, NavPage } from './components/layout/Sidebar';
import { Topbar } from './components/layout/Topbar';
import { ToastProvider } from './components/common/Toast';
import { AuthProvider } from './context/AuthContext';
import { AuthModal } from './components/auth/AuthModal';
import { HomePage } from './pages/HomePage';
import { DocumentsPage } from './pages/DocumentsPage';
import { DocumentDetailPage } from './pages/DocumentDetailPage';
import { AskQuestionsPage } from './pages/AskQuestionsPage';
import { SettingsPage } from './pages/SettingsPage';

export const AppContent: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<NavPage>('home');
  const [activeDocId, setActiveDocId] = useState<string>('');
  const [activeQuestion, setActiveQuestion] = useState<string>('');
  const [activeTopK, setActiveTopK] = useState<number>(5);
  const [searchQuery, setSearchQuery] = useState<string>('');

  const handleNavigate = (
    page: string,
    params?: { docId?: string; question?: string; topK?: number }
  ) => {
    if (params?.docId) {
      setActiveDocId(params.docId);
    }
    if (params?.question) {
      setActiveQuestion(params.question);
    }
    if (params?.topK) {
      setActiveTopK(params.topK);
    }

    if (page === 'doc-detail') {
      setCurrentPage('doc-detail');
    } else if (page === 'documents') {
      setCurrentPage('documents');
    } else if (page === 'ask') {
      setCurrentPage('ask');
    } else if (page === 'settings') {
      setCurrentPage('settings');
    } else {
      setCurrentPage('home');
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleGlobalSearch = (query: string) => {
    setSearchQuery(query);
  };

  return (
    <div className="app-container">
      {/* Left Sidebar */}
      <Sidebar
        currentPage={currentPage}
        onNavigate={(p) => handleNavigate(p)}
      />

      {/* Main Content Area */}
      <div className="main-wrapper">
        <Topbar onSearch={handleGlobalSearch} searchTerm={searchQuery} />

        <main style={{ flex: 1 }}>
          {currentPage === 'home' && (
            <HomePage
              onNavigate={handleNavigate}
              searchTerm={searchQuery}
            />
          )}

          {currentPage === 'documents' && (
            <DocumentsPage
              onNavigate={handleNavigate}
              initialSearch={searchQuery}
            />
          )}

          {currentPage === 'doc-detail' && (
            <DocumentDetailPage
              documentId={activeDocId}
              onBack={() => handleNavigate('documents')}
              onAskDoc={(docId) => handleNavigate('ask', { docId })}
            />
          )}

          {currentPage === 'ask' && (
            <AskQuestionsPage
              initialQuestion={activeQuestion}
              initialDocId={activeDocId}
              initialTopK={activeTopK}
              onInspectDocument={(docId) => handleNavigate('doc-detail', { docId })}
            />
          )}

          {currentPage === 'settings' && <SettingsPage />}
        </main>
      </div>

      <AuthModal />
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <ToastProvider>
        <AppContent />
      </ToastProvider>
    </AuthProvider>
  );
};

export default App;
