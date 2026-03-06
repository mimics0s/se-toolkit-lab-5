import React, { useState, useEffect } from 'react';
import { Bar, Line, Pie } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  PointElement,
  LineElement,
  ArcElement,
} from 'chart.js';

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  PointElement,
  LineElement,
  ArcElement
);

interface ChartData {
  labels: string[];
  datasets: {
    label: string;
    data: number[];
    backgroundColor: string | string[];
    borderColor?: string | string[];
    borderWidth?: number;
  }[];
}

const Dashboard: React.FC = () => {
  const [scoresData, setScoresData] = useState<ChartData | null>(null);
  const [timelineData, setTimelineData] = useState<ChartData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch scores data
        const scoresResponse = await fetch('/analytics/scores?lab=lab-04', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
          }
        });
        
        if (!scoresResponse.ok) {
          throw new Error('Failed to fetch scores');
        }
        
        const scores = await scoresResponse.json();
        
        // Prepare chart data for scores
        setScoresData({
          labels: scores.map((item: any) => item.bucket),
          datasets: [
            {
              label: 'Number of Students',
              data: scores.map((item: any) => item.count),
              backgroundColor: [
                'rgba(255, 99, 132, 0.5)',
                'rgba(54, 162, 235, 0.5)',
                'rgba(255, 206, 86, 0.5)',
                'rgba(75, 192, 192, 0.5)',
              ],
              borderColor: [
                'rgba(255, 99, 132, 1)',
                'rgba(54, 162, 235, 1)',
                'rgba(255, 206, 86, 1)',
                'rgba(75, 192, 192, 1)',
              ],
              borderWidth: 1,
            },
          ],
        });

        // Fetch timeline data
        const timelineResponse = await fetch('/analytics/timeline?lab=lab-04', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
          }
        });
        
        if (timelineResponse.ok) {
          const timeline = await timelineResponse.json();
          
          setTimelineData({
            labels: timeline.map((item: any) => item.date),
            datasets: [
              {
                label: 'Submissions',
                data: timeline.map((item: any) => item.submissions),
                backgroundColor: 'rgba(75, 192, 192, 0.5)',
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 1,
              },
            ],
          });
        }
        
        setLoading(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return <div style={{ padding: '20px', textAlign: 'center' }}>Loading dashboard data...</div>;
  }

  if (error) {
    return <div style={{ padding: '20px', color: 'red', textAlign: 'center' }}>Error: {error}</div>;
  }

  return (
    <div style={{ padding: '20px' }}>
      <h1>Analytics Dashboard</h1>
      
      <div style={{ marginBottom: '40px' }}>
        <h2>Score Distribution</h2>
        {scoresData && (
          <div style={{ height: '400px' }}>
            <Bar 
              data={scoresData} 
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: {
                    position: 'top' as const,
                  },
                  title: {
                    display: true,
                    text: 'Score Distribution by Bucket',
                  },
                },
              }}
            />
          </div>
        )}
      </div>

      {timelineData && (
        <div style={{ marginBottom: '40px' }}>
          <h2>Submission Timeline</h2>
          <div style={{ height: '400px' }}>
            <Line 
              data={timelineData} 
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: {
                    position: 'top' as const,
                  },
                  title: {
                    display: true,
                    text: 'Submissions Over Time',
                  },
                },
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
