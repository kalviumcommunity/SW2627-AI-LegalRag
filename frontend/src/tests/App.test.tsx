import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import App from '../App';

describe('App Routing & Shell Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    // Mock default documents list
    vi.spyOn(global, 'fetch').mockImplementation((url) => {
      const urlStr = String(url);
      if (urlStr.includes('/documents')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            items: [
              {
                document_id: 'doc-1',
                filename: 'Sample_Deed.pdf',
                source_type: 'pdf',
                status: 'processed',
                extracted_characters: 1540,
                chunk_count: 5,
                created_at: '2026-03-12T10:24:00Z',
              },
            ],
            total: 1,
            page: 1,
            page_size: 20,
            total_pages: 1,
          }),
        } as Response);
      }
      if (urlStr.includes('/health')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ status: 'healthy', app_name: 'property-api' }),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({}),
      } as Response);
    });
  });

  it('renders Sidebar with brand title and navigation items', async () => {
    await act(async () => {
      render(<App />);
    });
    expect(screen.getByText('PropIntel')).toBeInTheDocument();
    expect(screen.getByText('Your property files, decoded by AI.')).toBeInTheDocument();
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Documents')).toBeInTheDocument();
    expect(screen.getByText('Ask Questions')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('navigates to Documents page when clicking Documents nav item', async () => {
    await act(async () => {
      render(<App />);
    });

    const docNavBtn = screen.getByText('Documents');
    await act(async () => {
      fireEvent.click(docNavBtn);
    });

    await waitFor(() => {
      expect(screen.getByText('Property Documents')).toBeInTheDocument();
    });
  });

  it('navigates to Ask Questions page when clicking Ask Questions nav item', async () => {
    await act(async () => {
      render(<App />);
    });

    const askNavBtn = screen.getByText('Ask Questions');
    await act(async () => {
      fireEvent.click(askNavBtn);
    });

    await waitFor(() => {
      expect(screen.getByText('Ask Questions with AI')).toBeInTheDocument();
    });
  });

  it('navigates to Settings page when clicking Settings nav item', async () => {
    await act(async () => {
      render(<App />);
    });

    const settingsNavBtn = screen.getByText('Settings');
    await act(async () => {
      fireEvent.click(settingsNavBtn);
    });

    await waitFor(() => {
      expect(screen.getByText('System Settings & Status')).toBeInTheDocument();
      expect(screen.getByText('FastAPI Backend Service')).toBeInTheDocument();
    });
  });
});
