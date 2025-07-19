import React, { useState } from 'react';
import MultiDiseaseDataTables from './MultiDiseaseDataTables';

// Example usage of MultiDiseaseDataTables component
const MultiDiseaseDataTablesExample: React.FC = () => {
  // Example data structure for multiple diseases
  const [diseasesData] = useState([
    {
      diseaseId: 'diabetes',
      diseaseName: 'Diabetes',
      data: [
        {
          id: 1,
          title: 'Type 2 Diabetes Study',
          status: 'Active',
          phase: 'Phase 3',
          enrollment: 500,
          location: 'Multiple Sites',
          'metadata.sponsor': 'NIH',
          'metadata.start_date': '2024-01-15',
        },
        {
          id: 2,
          title: 'Insulin Resistance Trial',
          status: 'Recruiting',
          phase: 'Phase 2',
          enrollment: 200,
          location: 'Boston, MA',
          'metadata.sponsor': 'Pfizer',
          'metadata.start_date': '2024-03-01',
        },
      ],
      columns: [
        { key: 'title', label: 'Study Title', width: '300', sortable: true },
        { key: 'status', label: 'Status', width: '120', sortable: true },
        { key: 'phase', label: 'Phase', width: '100', sortable: true },
        { key: 'enrollment', label: 'Enrollment', width: '120', sortable: true },
        { key: 'location', label: 'Location', width: '200', sortable: true },
        { key: 'metadata.sponsor', label: 'Sponsor', width: '150', sortable: true },
        { key: 'metadata.start_date', label: 'Start Date', width: '120', sortable: true },
      ],
      totalCount: 2,
      loading: false,
    },
    {
      diseaseId: 'cancer',
      diseaseName: 'Cancer',
      data: [
        {
          id: 3,
          title: 'Breast Cancer Immunotherapy',
          status: 'Active',
          phase: 'Phase 3',
          enrollment: 800,
          location: 'Nationwide',
          'metadata.sponsor': 'Roche',
          'metadata.start_date': '2023-12-01',
        },
        {
          id: 4,
          title: 'Lung Cancer CAR-T Study',
          status: 'Recruiting',
          phase: 'Phase 1/2',
          enrollment: 150,
          location: 'New York, NY',
          'metadata.sponsor': 'Memorial Sloan Kettering',
          'metadata.start_date': '2024-02-15',
        },
        {
          id: 5,
          title: 'Prostate Cancer Prevention',
          status: 'Completed',
          phase: 'Phase 4',
          enrollment: 1200,
          location: 'International',
          'metadata.sponsor': 'Johnson & Johnson',
          'metadata.start_date': '2022-06-01',
        },
      ],
      columns: [
        { key: 'title', label: 'Study Title', width: '300', sortable: true },
        { key: 'status', label: 'Status', width: '120', sortable: true },
        { key: 'phase', label: 'Phase', width: '100', sortable: true },
        { key: 'enrollment', label: 'Enrollment', width: '120', sortable: true },
        { key: 'location', label: 'Location', width: '200', sortable: true },
        { key: 'metadata.sponsor', label: 'Sponsor', width: '150', sortable: true },
        { key: 'metadata.start_date', label: 'Start Date', width: '120', sortable: true },
      ],
      totalCount: 3,
      loading: false,
    },
    {
      diseaseId: 'cardiovascular',
      diseaseName: 'Cardiovascular Disease',
      data: [
        {
          id: 6,
          title: 'Heart Failure Treatment Study',
          status: 'Active',
          phase: 'Phase 3',
          enrollment: 600,
          location: 'Europe & US',
          'metadata.sponsor': 'Novartis',
          'metadata.start_date': '2024-01-10',
        },
        {
          id: 7,
          title: 'Cholesterol Reduction Trial',
          status: 'Recruiting',
          phase: 'Phase 2',
          enrollment: 300,
          location: 'California',
          'metadata.sponsor': 'Amgen',
          'metadata.start_date': '2024-04-01',
        },
      ],
      columns: [
        { key: 'title', label: 'Study Title', width: '300', sortable: true },
        { key: 'status', label: 'Status', width: '120', sortable: true },
        { key: 'phase', label: 'Phase', width: '100', sortable: true },
        { key: 'enrollment', label: 'Enrollment', width: '120', sortable: true },
        { key: 'location', label: 'Location', width: '200', sortable: true },
        { key: 'metadata.sponsor', label: 'Sponsor', width: '150', sortable: true },
        { key: 'metadata.start_date', label: 'Start Date', width: '120', sortable: true },
      ],
      totalCount: 2,
      loading: false,
    },
    {
      diseaseId: 'neurological',
      diseaseName: 'Neurological Disorders',
      data: [
        {
          id: 8,
          title: 'Alzheimer\'s Drug Trial',
          status: 'Active',
          phase: 'Phase 3',
          enrollment: 1000,
          location: 'Global',
          'metadata.sponsor': 'Biogen',
          'metadata.start_date': '2023-09-15',
        },
        {
          id: 9,
          title: 'Parkinson\'s Deep Brain Stimulation',
          status: 'Recruiting',
          phase: 'Phase 2',
          enrollment: 120,
          location: 'Cleveland, OH',
          'metadata.sponsor': 'Cleveland Clinic',
          'metadata.start_date': '2024-05-01',
        },
        {
          id: 10,
          title: 'Multiple Sclerosis Therapy',
          status: 'Active',
          phase: 'Phase 3',
          enrollment: 400,
          location: 'Canada & US',
          'metadata.sponsor': 'Sanofi',
          'metadata.start_date': '2024-02-01',
        },
      ],
      columns: [
        { key: 'title', label: 'Study Title', width: '300', sortable: true },
        { key: 'status', label: 'Status', width: '120', sortable: true },
        { key: 'phase', label: 'Phase', width: '100', sortable: true },
        { key: 'enrollment', label: 'Enrollment', width: '120', sortable: true },
        { key: 'location', label: 'Location', width: '200', sortable: true },
        { key: 'metadata.sponsor', label: 'Sponsor', width: '150', sortable: true },
        { key: 'metadata.start_date', label: 'Start Date', width: '120', sortable: true },
      ],
      totalCount: 3,
      loading: false,
    },
  ]);

  const handleRowClick = (row: any, diseaseId: string) => {
    console.log(`Row clicked in ${diseaseId}:`, row);
    // Handle row click - could open a modal, navigate to detail page, etc.
  };

  const handleExpandedContent = (row: any, diseaseId: string) => {
    return (
      <div style={{ padding: '16px', background: '#f8f9fa' }}>
        <h4>Study Details for {diseaseId}</h4>
        <p><strong>ID:</strong> {row.id}</p>
        <p><strong>Title:</strong> {row.title}</p>
        <p><strong>Sponsor:</strong> {row['metadata.sponsor']}</p>
        <p><strong>Start Date:</strong> {row['metadata.start_date']}</p>
      </div>
    );
  };

  return (
    <div style={{ padding: '20px' }}>
      <h1>Multi-Disease Clinical Trials Dashboard</h1>
      <p>
        This example demonstrates the MultiDiseaseDataTables component with sample data for 
        four different disease categories. Each table supports independent sorting, filtering, 
        selection, and column management.
      </p>
      
      <MultiDiseaseDataTables
        diseases={diseasesData}
        onRowClick={handleRowClick}
        expandedRowContent={handleExpandedContent}
      />
      
      <div style={{ marginTop: '40px', padding: '20px', background: '#f8f9fa', borderRadius: '8px' }}>
        <h3>Features:</h3>
        <ul>
          <li><strong>Individual CSV Export:</strong> Export each disease table separately to CSV</li>
          <li><strong>Excel Workbook Export:</strong> Export all tables to a single Excel file with multiple sheets</li>
          <li><strong>Row Selection:</strong> Select rows across tables for targeted exports</li>
          <li><strong>Independent Filtering:</strong> Each table has its own column filters</li>
          <li><strong>Responsive Design:</strong> Tables adapt to different screen sizes</li>
          <li><strong>Sorting & Pagination:</strong> Full TanStack Table functionality</li>
        </ul>
      </div>
    </div>
  );
};

export default MultiDiseaseDataTablesExample;