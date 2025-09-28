"""
Simple Web Dashboard for Discord Bot Monitoring
A lightweight Flask app to display bot metrics and health status.
"""

from flask import Flask, render_template, jsonify, request
import json
import sqlite3
from datetime import datetime, timedelta
import psutil
import asyncio
import os
from pathlib import Path

# Flask app with proper template and static directory paths
project_root = Path(__file__).parent.parent
app = Flask(__name__, 
            template_folder=str(project_root / 'templates'),
            static_folder=str(project_root / 'static'))

class DashboardData:
    def __init__(self, database_path=None):
        # Default to data folder database
        if database_path is None:
            self.database_path = str(project_root / 'data' / 'database.db')
        else:
            self.database_path = database_path
        self.metrics_file = "monitoring_metrics.json"
        
    def get_system_stats(self):
        """Get current system statistics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('.')
            
            # Database size
            db_size = 0
            if Path(self.database_path).exists():
                db_size = Path(self.database_path).stat().st_size / (1024 * 1024)  # MB
            
            return {
                'cpu_percent': round(cpu_percent, 1),
                'memory_percent': round(memory.percent, 1),
                'memory_used_gb': round(memory.used / (1024**3), 2),
                'memory_total_gb': round(memory.total / (1024**3), 2),
                'disk_percent': round(disk.percent, 1),
                'disk_free_gb': round(disk.free / (1024**3), 2),
                'database_size_mb': round(db_size, 2)
            }
        except Exception as e:
            return {'error': str(e)}
            
    def get_bot_stats(self):
        """Get bot statistics from database"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            # Total users across all guilds
            cursor.execute("SELECT COUNT(DISTINCT discord_id) FROM users")
            total_users = cursor.fetchone()[0] or 0
            
            # Users per guild
            cursor.execute("""
                SELECT guild_id, COUNT(discord_id) as user_count 
                FROM users 
                GROUP BY guild_id 
                ORDER BY user_count DESC
            """)
            guild_stats = cursor.fetchall()
            
            # Recent registrations (last 7 days)
            week_ago = datetime.now() - timedelta(days=7)
            cursor.execute("SELECT COUNT(*) FROM users WHERE created_at >= ?", (week_ago.isoformat(),))
            recent_registrations = cursor.fetchone()[0] or 0
            
            # Database tables info
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            table_names = [row[0] for row in cursor.fetchall()]
            
            # Check which tables have guild_id
            guild_ready_tables = []
            for table in table_names:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [col[1] for col in cursor.fetchall()]
                if 'guild_id' in columns:
                    guild_ready_tables.append(table)
            
            conn.close()
            
            return {
                'total_users': total_users,
                'guild_count': len(guild_stats),
                'guild_stats': guild_stats[:10],  # Top 10 guilds by user count
                'recent_registrations': recent_registrations,
                'total_tables': len(table_names),
                'guild_ready_tables': len(guild_ready_tables),
                'guild_readiness_percent': round((len(guild_ready_tables) / len(table_names)) * 100, 1)
            }
        except Exception as e:
            return {'error': str(e)}
            
    def get_metrics_history(self):
        """Get historical metrics from file"""
        try:
            if Path(self.metrics_file).exists():
                with open(self.metrics_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            return {'error': str(e)}
            
    def get_health_status(self):
        """Get overall health status"""
        system_stats = self.get_system_stats()
        bot_stats = self.get_bot_stats()
        
        health = {
            'status': 'healthy',
            'issues': []
        }
        
        # Check system health
        if system_stats.get('cpu_percent', 0) > 80:
            health['issues'].append(f"High CPU usage: {system_stats['cpu_percent']}%")
            health['status'] = 'warning'
            
        if system_stats.get('memory_percent', 0) > 85:
            health['issues'].append(f"High memory usage: {system_stats['memory_percent']}%")
            health['status'] = 'warning'
            
        if system_stats.get('disk_percent', 0) > 90:
            health['issues'].append(f"Low disk space: {system_stats['disk_percent']}% used")
            health['status'] = 'critical'
            
        # Check database existence
        if not Path(self.database_path).exists():
            health['issues'].append("Database file not found")
            health['status'] = 'critical'
            
        return health

dashboard_data = DashboardData()

@app.route('/')
def index():
    """Main dashboard page"""
    system_stats = dashboard_data.get_system_stats()
    bot_stats = dashboard_data.get_bot_stats()
    health = dashboard_data.get_health_status()
    
    return render_template('dashboard.html', 
                         system_stats=system_stats,
                         bot_stats=bot_stats,
                         health=health,
                         timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

@app.route('/api/stats')
def api_stats():
    """API endpoint for stats (for AJAX updates)"""
    return jsonify({
        'system': dashboard_data.get_system_stats(),
        'bot': dashboard_data.get_bot_stats(),
        'health': dashboard_data.get_health_status(),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/guilds')
def api_guilds():
    """API endpoint for guild statistics"""
    try:
        conn = sqlite3.connect(dashboard_data.database_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT guild_id, COUNT(discord_id) as user_count,
                   MIN(created_at) as first_user,
                   MAX(created_at) as last_user
            FROM users 
            GROUP BY guild_id 
            ORDER BY user_count DESC
        """)
        
        guilds = []
        for row in cursor.fetchall():
            guilds.append({
                'guild_id': row[0],
                'user_count': row[1],
                'first_user': row[2],
                'last_user': row[3]
            })
            
        conn.close()
        return jsonify(guilds)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Dashboard is optional in hosted environments. Enable with ENABLE_DASHBOARD=1
    if os.getenv('ENABLE_DASHBOARD', '0') not in ('1', 'true', 'True'):
        print('Monitoring dashboard disabled (set ENABLE_DASHBOARD=1 to enable)')
        raise SystemExit(0)

    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Create basic HTML template if it doesn't exist
    template_path = Path('templates/dashboard.html')
    if not template_path.exists():
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Discord Bot Monitoring Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 20px; 
            background-color: #f5f5f5; 
        }
        .container { 
            max-width: 1200px; 
            margin: 0 auto; 
        }
        .header { 
            background: #2c3e50; 
            color: white; 
            padding: 20px; 
            border-radius: 8px; 
            margin-bottom: 20px; 
        }
        .stats-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
            gap: 20px; 
            margin-bottom: 20px; 
        }
        .stat-card { 
            background: white; 
            padding: 20px; 
            border-radius: 8px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
        }
        .stat-card h3 { 
            margin-top: 0; 
            color: #2c3e50; 
        }
        .health-healthy { color: #27ae60; font-weight: bold; }
        .health-warning { color: #f39c12; font-weight: bold; }
        .health-critical { color: #e74c3c; font-weight: bold; }
        .metric { 
            display: flex; 
            justify-content: space-between; 
            margin: 10px 0; 
            padding: 5px 0; 
            border-bottom: 1px solid #eee; 
        }
        .progress-bar { 
            width: 100%; 
            height: 10px; 
            background: #ecf0f1; 
            border-radius: 5px; 
            overflow: hidden; 
            margin: 5px 0; 
        }
        .progress-fill { 
            height: 100%; 
            transition: width 0.3s ease; 
        }
        .progress-normal { background: #27ae60; }
        .progress-warning { background: #f39c12; }
        .progress-critical { background: #e74c3c; }
        .guild-list { 
            max-height: 300px; 
            overflow-y: auto; 
        }
        .footer { 
            text-align: center; 
            margin-top: 20px; 
            color: #7f8c8d; 
        }
    </style>
    <script>
        function updateStats() {
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    // Update timestamp
                    document.getElementById('timestamp').textContent = new Date(data.timestamp).toLocaleString();
                    
                    // Update system stats
                    if (data.system) {
                        updateProgressBar('cpu', data.system.cpu_percent);
                        updateProgressBar('memory', data.system.memory_percent);
                        updateProgressBar('disk', data.system.disk_percent);
                        
                        document.getElementById('memory-usage').textContent = 
                            `${data.system.memory_used_gb} GB / ${data.system.memory_total_gb} GB`;
                        document.getElementById('disk-free').textContent = `${data.system.disk_free_gb} GB free`;
                        document.getElementById('db-size').textContent = `${data.system.database_size_mb} MB`;
                    }
                    
                    // Update health status
                    if (data.health) {
                        const healthElement = document.getElementById('health-status');
                        healthElement.textContent = data.health.status.toUpperCase();
                        healthElement.className = `health-${data.health.status}`;
                        
                        const issuesElement = document.getElementById('health-issues');
                        if (data.health.issues.length > 0) {
                            issuesElement.innerHTML = '<ul><li>' + data.health.issues.join('</li><li>') + '</li></ul>';
                        } else {
                            issuesElement.innerHTML = '<p style="color: #27ae60;">All systems operational</p>';
                        }
                    }
                })
                .catch(error => console.error('Error updating stats:', error));
        }
        
        function updateProgressBar(type, percent) {
            const bar = document.getElementById(type + '-progress');
            const text = document.getElementById(type + '-percent');
            
            if (bar && text) {
                bar.style.width = percent + '%';
                text.textContent = percent + '%';
                
                // Update color based on percentage
                bar.className = 'progress-fill ' + 
                    (percent > 85 ? 'progress-critical' : 
                     percent > 70 ? 'progress-warning' : 'progress-normal');
            }
        }
        
        // Auto-update every 30 seconds
        setInterval(updateStats, 30000);
        
        // Update on page load
        window.addEventListener('load', updateStats);
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Discord Bot Monitoring Dashboard</h1>
            <p>Multi-Guild Bot Status & Metrics</p>
            <p><small>Last updated: <span id="timestamp">{{ timestamp }}</span></small></p>
        </div>
        
        <div class="stats-grid">
            <!-- Health Status -->
            <div class="stat-card">
                <h3>🏥 Health Status</h3>
                <div class="metric">
                    <span>Status:</span>
                    <span id="health-status" class="health-{{ health.status }}">{{ health.status.upper() }}</span>
                </div>
                <div id="health-issues">
                    {% if health.issues %}
                        <ul>
                        {% for issue in health.issues %}
                            <li>{{ issue }}</li>
                        {% endfor %}
                        </ul>
                    {% else %}
                        <p style="color: #27ae60;">All systems operational</p>
                    {% endif %}
                </div>
            </div>
            
            <!-- System Resources -->
            <div class="stat-card">
                <h3>🖥️ System Resources</h3>
                <div class="metric">
                    <span>CPU Usage:</span>
                    <span id="cpu-percent">{{ system_stats.cpu_percent }}%</span>
                </div>
                <div class="progress-bar">
                    <div id="cpu-progress" class="progress-fill progress-normal" style="width: {{ system_stats.cpu_percent }}%"></div>
                </div>
                
                <div class="metric">
                    <span>Memory:</span>
                    <span id="memory-percent">{{ system_stats.memory_percent }}%</span>
                </div>
                <div class="progress-bar">
                    <div id="memory-progress" class="progress-fill progress-normal" style="width: {{ system_stats.memory_percent }}%"></div>
                </div>
                <small id="memory-usage">{{ system_stats.memory_used_gb }} GB / {{ system_stats.memory_total_gb }} GB</small>
                
                <div class="metric">
                    <span>Disk Usage:</span>
                    <span id="disk-percent">{{ system_stats.disk_percent }}%</span>
                </div>
                <div class="progress-bar">
                    <div id="disk-progress" class="progress-fill progress-normal" style="width: {{ system_stats.disk_percent }}%"></div>
                </div>
                <small id="disk-free">{{ system_stats.disk_free_gb }} GB free</small>
            </div>
            
            <!-- Bot Statistics -->
            <div class="stat-card">
                <h3>🤖 Bot Statistics</h3>
                <div class="metric">
                    <span>Total Users:</span>
                    <span>{{ bot_stats.total_users }}</span>
                </div>
                <div class="metric">
                    <span>Guilds:</span>
                    <span>{{ bot_stats.guild_count }}</span>
                </div>
                <div class="metric">
                    <span>Recent Registrations (7d):</span>
                    <span>{{ bot_stats.recent_registrations }}</span>
                </div>
                <div class="metric">
                    <span>Database Size:</span>
                    <span id="db-size">{{ system_stats.database_size_mb }} MB</span>
                </div>
            </div>
            
            <!-- Multi-Guild Progress -->
            <div class="stat-card">
                <h3>🌐 Multi-Guild Progress</h3>
                <div class="metric">
                    <span>Guild-Ready Tables:</span>
                    <span>{{ bot_stats.guild_ready_tables }}/{{ bot_stats.total_tables }}</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill progress-normal" style="width: {{ bot_stats.guild_readiness_percent }}%"></div>
                </div>
                <small>{{ bot_stats.guild_readiness_percent }}% Complete</small>
                
                <div style="margin-top: 15px;">
                    <strong>Migration Status:</strong>
                    {% if bot_stats.guild_readiness_percent >= 60 %}
                        <span style="color: #27ae60;">✅ Ready for multi-guild deployment</span>
                    {% elif bot_stats.guild_readiness_percent >= 40 %}
                        <span style="color: #f39c12;">⚠️ Partial multi-guild support</span>
                    {% else %}
                        <span style="color: #e74c3c;">❌ Single-guild only</span>
                    {% endif %}
                </div>
            </div>
            
            <!-- Top Guilds by Users -->
            <div class="stat-card">
                <h3>🏆 Top Guilds by Users</h3>
                <div class="guild-list">
                    {% for guild in bot_stats.guild_stats %}
                        <div class="metric">
                            <span>Guild {{ guild[0] }}:</span>
                            <span>{{ guild[1] }} users</span>
                        </div>
                    {% endfor %}
                </div>
            </div>
        </div>
        
        <div class="footer">
            <p>Discord Bot Monitoring Dashboard | Auto-updates every 30 seconds</p>
        </div>
    </div>
</body>
</html>
        """
        
        with open(template_path, 'w') as f:
            f.write(html_template)
        
        print("Created dashboard template")
    
    # Bind to the PORT provided by Railway or default to 5000 for local testing
    try:
        port = int(os.getenv('PORT', '5000'))
    except Exception:
        port = 5000

    print(f"Starting monitoring dashboard on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)