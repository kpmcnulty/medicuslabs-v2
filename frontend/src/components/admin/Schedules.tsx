import React, { useEffect, useState } from 'react';
import { adminApi } from '../../api/admin';
import './Schedules.css';

interface Schedule {
  name: string;
  task: string;
  enabled: boolean;
  description: string | null;
  schedule: {
    type: string;
    minute?: string;
    hour?: string;
    day_of_week?: string;
    day_of_month?: string;
    month_of_year?: string;
    seconds?: number;
  };
  args: any[];
  kwargs: Record<string, any>;
  last_run_at: string | null;
  total_run_count: number | null;
}

interface CronSchedule {
  minute: string;
  hour: string;
  day_of_week: string;
  day_of_month: string;
  month_of_year: string;
}

const Schedules: React.FC = () => {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingSchedule, setEditingSchedule] = useState<Schedule | null>(null);
  const [showCustomScrape, setShowCustomScrape] = useState(false);
  const [diseaseTerm, setDiseaseTerm] = useState('');
  const [selectedSources, setSelectedSources] = useState<string[]>(['clinicaltrials', 'pubmed', 'reddit']);
  const [cronForm, setCronForm] = useState<CronSchedule>({
    minute: '*',
    hour: '*',
    day_of_week: '*',
    day_of_month: '*',
    month_of_year: '*'
  });

  useEffect(() => {
    loadSchedules();
  }, []);

  const loadSchedules = async () => {
    try {
      setLoading(true);
      const data = await adminApi.getSchedules();
      setSchedules(data);
    } catch (err) {
      setError('Failed to load schedules');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleEnabled = async (schedule: Schedule) => {
    try {
      await adminApi.updateSchedule(schedule.name, { enabled: !schedule.enabled });
      await loadSchedules();
    } catch (err) {
      console.error('Failed to update schedule:', err);
    }
  };

  const handleRunNow = async (scheduleName: string) => {
    try {
      const result = await adminApi.runScheduleNow(scheduleName);
      alert(`✅ Schedule triggered successfully!\n\nTask ID: ${result.task_id}\nSchedule: ${result.schedule_name}\n\nCheck the Jobs page to monitor progress.`);
    } catch (err) {
      alert('❌ Failed to trigger schedule');
      console.error(err);
    }
  };

  const handleEditSchedule = (schedule: Schedule) => {
    setEditingSchedule(schedule);
    if (schedule.schedule.type === 'crontab') {
      setCronForm({
        minute: schedule.schedule.minute || '*',
        hour: schedule.schedule.hour || '*',
        day_of_week: schedule.schedule.day_of_week || '*',
        day_of_month: schedule.schedule.day_of_month || '*',
        month_of_year: schedule.schedule.month_of_year || '*'
      });
    }
  };

  const handleSaveCron = async () => {
    if (!editingSchedule) return;

    try {
      await adminApi.updateSchedule(editingSchedule.name, { cron: cronForm });
      alert('✅ Schedule updated!\n\nNote: Celery beat restart required for changes to take effect.');
      setEditingSchedule(null);
      await loadSchedules();
    } catch (err) {
      alert('❌ Failed to update schedule');
      console.error(err);
    }
  };

  const handleCustomScrape = async () => {
    if (!diseaseTerm.trim()) {
      alert('Please enter a disease term');
      return;
    }

    try {
      const result = await adminApi.triggerDiseaseScrape(diseaseTerm, selectedSources);
      alert(`✅ Custom scrape triggered!\n\nTask ID: ${result.task_id}\nDisease: ${result.disease_term}\nSources: ${result.sources.join(', ')}\n\nCheck the Jobs page to monitor progress.`);
      setDiseaseTerm('');
    } catch (err) {
      alert('❌ Failed to trigger custom scrape');
      console.error(err);
    }
  };

  const formatCronExpression = (schedule: Schedule) => {
    if (schedule.schedule.type === 'crontab') {
      const { minute, hour, day_of_week, day_of_month, month_of_year } = schedule.schedule;
      return `${minute} ${hour} ${day_of_month} ${month_of_year} ${day_of_week}`;
    }
    return `Every ${schedule.schedule.seconds} seconds`;
  };

  const getCronDescription = (schedule: Schedule) => {
    if (schedule.schedule.type !== 'crontab') {
      return `Runs every ${schedule.schedule.seconds} seconds`;
    }

    const { minute, hour, day_of_week, day_of_month, month_of_year } = schedule.schedule;
    
    // Simple human-readable descriptions for common patterns
    if (minute === '0' && hour === '2' && day_of_week === '*' && day_of_month === '*' && month_of_year === '*') {
      return 'Daily at 2:00 AM';
    } else if (minute === '0' && hour === '3' && day_of_week === '0' && day_of_month === '*' && month_of_year === '*') {
      return 'Weekly on Sundays at 3:00 AM';
    } else if (minute === '0' && hour === '*' && day_of_week === '*' && day_of_month === '*' && month_of_year === '*') {
      return 'Every hour at minute 0';
    }
    
    return 'Custom schedule';
  };

  if (loading) return <div className="loading">Loading schedules...</div>;
  if (error) return <div className="error">{error}</div>;

  return (
    <div className="schedules-container">
      <div className="schedules-header">
        <h1>Schedule Management</h1>
        <div className="schedules-actions">
          <a 
            href="http://localhost:5555" 
            target="_blank" 
            rel="noopener noreferrer" 
            className="flower-link"
          >
            🌸 Open Flower Monitor
          </a>
        </div>
      </div>

      <div className="schedules-grid">
        {schedules.map((schedule) => (
          <div key={schedule.name} className="schedule-card">
            <div className="schedule-header">
              <h3 className="schedule-name">{schedule.name.replace(/_/g, ' ').toUpperCase()}</h3>
              <label className="toggle-switch">
                <input
                  type="checkbox"
                  checked={schedule.enabled}
                  onChange={() => handleToggleEnabled(schedule)}
                />
                <span className="toggle-slider"></span>
              </label>
            </div>
            
            {schedule.description && (
              <p className="schedule-description">{schedule.description}</p>
            )}

            <div className="schedule-details">
              <div className="schedule-detail">
                <span className="schedule-detail-label">Status:</span>
                <span className={schedule.enabled ? 'status-active' : 'status-disabled'}>
                  {schedule.enabled ? 'Active' : 'Disabled'}
                </span>
              </div>
              <div className="schedule-detail">
                <span className="schedule-detail-label">Schedule:</span>
                <span className="schedule-detail-value">{getCronDescription(schedule)}</span>
              </div>
              <div className="schedule-detail">
                <span className="schedule-detail-label">Cron:</span>
                <span className="cron-expression">{formatCronExpression(schedule)}</span>
              </div>
              {schedule.last_run_at && (
                <div className="schedule-detail">
                  <span className="schedule-detail-label">Last Run:</span>
                  <span className="schedule-detail-value">
                    {new Date(schedule.last_run_at).toLocaleString()}
                  </span>
                </div>
              )}
            </div>

            <div className="schedule-actions">
              <button
                className="btn-sm btn-primary"
                onClick={() => handleRunNow(schedule.name)}
                disabled={!schedule.enabled}
                title={schedule.enabled ? "Run this schedule immediately" : "Enable schedule first"}
              >
                Run Now
              </button>
              <button
                className="btn-sm"
                onClick={() => handleEditSchedule(schedule)}
              >
                Edit Schedule
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="custom-scrape-section">
        <h2>Custom Disease Scraping</h2>
        <p className="schedule-description">
          Trigger an on-demand scrape for a specific disease term across selected sources.
        </p>
        <div className="custom-scrape-form">
          <div className="form-group">
            <label>Disease Term</label>
            <input
              type="text"
              value={diseaseTerm}
              onChange={(e) => setDiseaseTerm(e.target.value)}
              placeholder="e.g., Type 2 Diabetes"
            />
          </div>
          <div className="form-group">
            <label>Sources</label>
            <select
              multiple
              value={selectedSources}
              onChange={(e) => {
                const selected = Array.from(e.target.selectedOptions, option => option.value);
                setSelectedSources(selected);
              }}
            >
              <option value="clinicaltrials">ClinicalTrials.gov</option>
              <option value="pubmed">PubMed</option>
              <option value="reddit">Reddit</option>
            </select>
            <small>Hold Ctrl/Cmd to select multiple</small>
          </div>
          <button
            className="btn-sm btn-success"
            onClick={handleCustomScrape}
          >
            Start Scraping
          </button>
        </div>
      </div>

      {editingSchedule && (
        <div className="modal-overlay" onClick={() => setEditingSchedule(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Edit Schedule: {editingSchedule.name}</h2>
            
            {editingSchedule.schedule.type === 'crontab' && (
              <>
                <div className="cron-editor">
                  <div className="cron-field">
                    <label>Minute</label>
                    <input
                      type="text"
                      value={cronForm.minute}
                      onChange={(e) => setCronForm({ ...cronForm, minute: e.target.value })}
                      placeholder="0-59"
                    />
                  </div>
                  <div className="cron-field">
                    <label>Hour</label>
                    <input
                      type="text"
                      value={cronForm.hour}
                      onChange={(e) => setCronForm({ ...cronForm, hour: e.target.value })}
                      placeholder="0-23"
                    />
                  </div>
                  <div className="cron-field">
                    <label>Day of Month</label>
                    <input
                      type="text"
                      value={cronForm.day_of_month}
                      onChange={(e) => setCronForm({ ...cronForm, day_of_month: e.target.value })}
                      placeholder="1-31"
                    />
                  </div>
                  <div className="cron-field">
                    <label>Month</label>
                    <input
                      type="text"
                      value={cronForm.month_of_year}
                      onChange={(e) => setCronForm({ ...cronForm, month_of_year: e.target.value })}
                      placeholder="1-12"
                    />
                  </div>
                  <div className="cron-field">
                    <label>Day of Week</label>
                    <input
                      type="text"
                      value={cronForm.day_of_week}
                      onChange={(e) => setCronForm({ ...cronForm, day_of_week: e.target.value })}
                      placeholder="0-6 (Sun-Sat)"
                    />
                  </div>
                </div>

                <div className="cron-preview">
                  <div className="cron-preview-label">Cron Expression:</div>
                  <div className="cron-preview-value">
                    {`${cronForm.minute} ${cronForm.hour} ${cronForm.day_of_month} ${cronForm.month_of_year} ${cronForm.day_of_week}`}
                  </div>
                </div>

                <p className="schedule-description">
                  Note: Use * for any value, comma-separated values (1,3,5), ranges (1-5), or steps (*/5)
                </p>
              </>
            )}

            <div className="modal-actions">
              <button className="btn-sm btn-primary" onClick={handleSaveCron}>
                Save Changes
              </button>
              <button className="btn-sm" onClick={() => setEditingSchedule(null)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Schedules;