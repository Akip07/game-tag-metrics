from flask import Flask, render_template, jsonify
import json
import os
from main import (
    read_game_tags,
    read_reviews,
    compute_tag_averages,
    compute_user_agreement,
    build_tag_network,
)
import plotly
import plotly.graph_objects as go
import plotly.express as px


app = Flask(__name__)

# Load data on startup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REVIEWS_PATH = os.path.join(BASE_DIR, "reviews.csv")
TAGS_PATH = os.path.join(BASE_DIR, "gametags.json")

game_tags = read_game_tags(TAGS_PATH)
users, reviews = read_reviews(REVIEWS_PATH)
tag_averages, tag_stats, _ = compute_tag_averages(users, reviews, game_tags, min_count=3)


@app.route("/")
def index():
    return render_template("index.html", users=users)


@app.route("/api/user-tags/<user>")
def user_tags(user):
    """Return top tags for a user as interactive chart data."""
    if user not in tag_averages:
        return jsonify({"error": "User not found"}), 404
    
    tags = tag_averages[user]
    if not tags:
        return jsonify({"error": "No tags for user"}), 404
    
    top_tags = sorted(tags.items(), key=lambda item: item[1], reverse=True)[:10]
    labels = [item[0] for item in top_tags][::-1]
    values = [item[1] for item in top_tags][::-1]
    
    fig = go.Figure(data=[
        go.Bar(x=values, y=labels, orientation='h', marker_color='#4C78A8')
    ])
    fig.update_layout(
        title=f"Top tags for {user}",
        xaxis_title="Average score per tagged game",
        yaxis_title="Tags",
        height=500,
        margin=dict(l=200, r=50, t=50, b=50)
    )
    
    return jsonify(json.loads(plotly.io.to_json(fig)))


@app.route("/api/tag-heatmap")
def tag_heatmap():
    """Return tag heatmap across users."""
    tags = sorted(tag for tag, stats in tag_stats.items() if stats["count"] >= 3)
    if not tags:
        return jsonify({"error": "No tags found"}), 404
    
    values = []
    for tag in tags:
        count = tag_stats[tag]["count"]
        row = []
        for user in users:
            row.append(tag_stats[tag]["sums"][user] / count if count else 0.0)
        values.append(row)
    
    fig = go.Figure(data=go.Heatmap(
        z=values,
        y=tags,
        x=users,
        colorscale='Viridis',
        colorbar=dict(title="Avg score")
    ))
    fig.update_layout(
        title="Tag preferences across users",
        height=max(500, len(tags) * 20),
        margin=dict(b=100)
    )
    
    return jsonify(json.loads(plotly.io.to_json(fig)))


@app.route("/api/tag-counts")
def tag_counts():
    """Return tag frequency treemap."""
    items = [(tag, stats) for tag, stats in tag_stats.items() if stats["count"] >= 3]
    items = sorted(items, key=lambda item: item[1]["count"], reverse=True)
    
    if not items:
        return jsonify({"error": "No tags found"}), 404
    
    labels = [tag for tag, _ in items]
    counts = [stats["count"] for _, stats in items]
    
    fig = go.Figure(go.Treemap(
        labels=labels,
        parents=[""] * len(labels),
        values=counts,
        textposition="middle center",
    ))
    fig.update_layout(
        title="Tag frequency across games",
        height=600,
    )
    
    return jsonify(json.loads(plotly.io.to_json(fig)))


@app.route("/api/user-agreement")
def user_agreement():
    """Return user agreement/correlation matrix."""
    correlation_matrix = compute_user_agreement(users, reviews)
    
    fig = go.Figure(data=go.Heatmap(
        z=correlation_matrix,
        x=users,
        y=users,
        colorscale='RdYlGn',
        zmin=0,
        zmax=1,
        text=[[f"{correlation_matrix[i][j]:.2f}" for j in range(len(users))] for i in range(len(users))],
        texttemplate="%{text}",
        textfont={"size": 14},
        hovertemplate='%{y} vs %{x}<br>Correlation: %{z:.2f}<extra></extra>',
        colorbar=dict(title="Correlation")
    ))
    fig.update_layout(
        title="User agreement matrix",
        height=500,
    )
    
    return jsonify(json.loads(plotly.io.to_json(fig)))


@app.route("/api/tag-network")
def tag_network():
    """Return tag co-occurrence network."""
    import networkx as nx
    
    G = build_tag_network(game_tags)
    
    if len(G.nodes()) == 0:
        return jsonify({"error": "No network data"}), 404
    
    pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
    
    edge_x = []
    edge_y = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.append(x0)
        edge_x.append(x1)
        edge_x.append(None)
        edge_y.append(y0)
        edge_y.append(y1)
        edge_y.append(None)
    
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        mode='lines',
        line=dict(width=0.5, color='#888'),
        hoverinfo='none',
        showlegend=False
    )
    
    node_x = []
    node_y = []
    node_color = []
    node_text = []
    
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_color.append(G.degree(node))
        node_text.append(node)
    
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        text=node_text,
        textposition="top center",
        hoverinfo='text',
        hovertext=node_text,
        marker=dict(
            showscale=True,
            color=node_color,
            size=25,
            colorscale='YlOrRd',
            line_width=2
        ),
        showlegend=False
    )
    
    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        title="Tag Co-occurrence Network",
        showlegend=False,
        hovermode='closest',
        margin=dict(b=20, l=5, r=5, t=40),
        annotations=[dict(
            text="Nodes represent tags, edges show co-occurrence in games",
            showarrow=False,
            xref="paper", yref="paper",
            x=0.005, y=-0.002
        )],
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=600,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, showticklabels=False)
    fig.update_yaxes(showgrid=False, zeroline=False, showticklabels=False)
    
    return jsonify(json.loads(plotly.io.to_json(fig)))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
