import csv
import json
import os
import re
import unicodedata

import matplotlib.pyplot as plt
import networkx as nx
import squarify


EXCLUDED_TAGS = {
	"multiplayer",
	"co-op",
	"online co-op",
	"singleplayer",
	"character customization",
	"early access",
	"controller",
	"great soundtrack",
	"local co-op",
	"massively multiplayer",
	"moddable",
	"local multiplayer",
	"4 player local",
}


def normalize_key(text: str) -> str:
	normalized = unicodedata.normalize("NFKD", text)
	ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
	return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())


def parse_rating(value: str):
	if value is None:
		return None
	value = value.strip()
	if not value:
		return None
	try:
		return float(value)
	except ValueError:
		return None


def read_game_tags(path: str):
	game_tags = {}
	with open(path, "r", encoding="utf-8") as file:
		data = json.load(file)
		for game, tags_data in data.items():
			if isinstance(tags_data, dict):
				tags = list(tags_data.keys())
			elif isinstance(tags_data, list):
				tags = tags_data
			else:
				tags = []
			# Skip games with no tags
			if not tags:
				continue
			game_tags[normalize_key(game)] = {"name": game, "tags": tags}
	return game_tags


def read_reviews(path: str):
	with open(path, "r", encoding="utf-8", newline="") as file:
		reader = csv.reader(file)
		header = next(reader, None)
		if not header:
			return [], []
		users = [col.strip() for col in header[1:] if col.strip() and col.strip().lower() != "suma"]
		rows = []
		for row in reader:
			if not row:
				continue
			game = row[0].strip()
			ratings = {}
			for index, user in enumerate(users, start=1):
				rating = parse_rating(row[index] if index < len(row) else "")
				ratings[user] = rating
			rows.append({"game": game, "ratings": ratings})
	return users, rows


def build_alias_map():
	alias_raw = {
		"Fly Knight 2": "FlyKnight",
		"Void Crew (PULSAR 2.0)": "Void Crew",
		"BigWalk (wychodzi w 2026)": "BigWalk",
		"Deep Dish Dungeon (kiedyś wyjdzie)": "Deep Dish Dungeon",
	}
	return {normalize_key(key): value for key, value in alias_raw.items()}


def compute_tag_averages(users, reviews, game_tags, min_count=3):
	alias_map = build_alias_map()
	tag_stats = {}
	unmatched = []

	for entry in reviews:
		game = entry["game"]
		normalized_game = normalize_key(game)
		if normalized_game in alias_map:
			normalized_game = normalize_key(alias_map[normalized_game])

		tag_entry = game_tags.get(normalized_game)
		if not tag_entry:
			unmatched.append(game)
			continue

		tags = tag_entry["tags"]
		for tag in tags:
			if tag.strip().casefold() in EXCLUDED_TAGS:
				continue
			stats = tag_stats.setdefault(tag, {"count": 0, "sums": {user: 0.0 for user in users}})
			stats["count"] += 1
			for user in users:
				rating = entry["ratings"].get(user)
				stats["sums"][user] += rating if rating is not None else 0.0

	tag_averages = {user: {} for user in users}
	for tag, stats in tag_stats.items():
		count = stats["count"]
		if count < min_count:
			continue
		for user in users:
			tag_averages[user][tag] = stats["sums"][user] / count

	return tag_averages, tag_stats, unmatched


def sanitize_filename(text: str) -> str:
	cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", text.strip())
	return cleaned.strip("_") or "user"


def plot_user_tags(tag_averages, output_dir, top_n=10):
	os.makedirs(output_dir, exist_ok=True)
	for user, tags in tag_averages.items():
		if not tags:
			continue
		top_tags = sorted(tags.items(), key=lambda item: item[1], reverse=True)[:top_n]
		labels = [item[0] for item in top_tags][::-1]
		values = [item[1] for item in top_tags][::-1]

		plt.figure(figsize=(10, 6))
		plt.barh(labels, values, color="#4C78A8")
		plt.xlabel("Average score per tagged game")
		plt.title(f"Top tags for {user}")
		plt.tight_layout()

		filename = f"tag_preferences_{sanitize_filename(user)}.png"
		plt.savefig(os.path.join(output_dir, filename), dpi=150)
		plt.close()


def plot_tag_heatmap(tag_stats, users, output_path, min_count=3):
	if not tag_stats:
		return

	tags = sorted(tag for tag, stats in tag_stats.items() if stats["count"] >= min_count)
	if not tags:
		print(f"No tags found with at least {min_count} games for the heatmap.")
		return
	values = []
	for tag in tags:
		count = tag_stats[tag]["count"]
		row = []
		for user in users:
			row.append(tag_stats[tag]["sums"][user] / count if count else 0.0)
		values.append(row)

	plt.figure(figsize=(max(10, len(users) * 1.2), max(8, len(tags) * 0.35)))
	image = plt.imshow(values, aspect="auto", cmap="viridis")
	plt.colorbar(image, label="Average score per tagged game")
	plt.yticks(range(len(tags)), tags)
	plt.xticks(range(len(users)), users, rotation=45, ha="right")
	plt.tight_layout()
	plt.savefig(output_path, dpi=150)
	plt.close()


def plot_tag_counts_treemap(tag_stats, output_path, min_count=3):
	if not tag_stats:
		return

	items = [item for item in tag_stats.items() if item[1]["count"] >= min_count]
	items = sorted(items, key=lambda item: item[1]["count"], reverse=True)

	if not items:
		return

	labels = [tag for tag, _ in items]
	counts = [stats["count"] for _, stats in items]

	plt.figure(figsize=(14, 10))
	# Create softer, pastel-like colors by blending with white
	base_colors = [plt.cm.hsv(i / len(labels)) for i in range(len(labels))]
	colors = [(r * 0.6 + 1 * 0.4, g * 0.6 + 1 * 0.4, b * 0.6 + 1 * 0.4, a) for r, g, b, a in base_colors]
	squarify.plot(sizes=counts, label=labels, ax=plt.gca(), color=colors, text_kwargs={"fontsize": 9})
	plt.title("Tag frequency across games", fontsize=16, fontweight="bold")
	plt.axis("off")
	plt.tight_layout()
	plt.savefig(output_path, dpi=150, bbox_inches="tight")
	plt.close()


def compute_user_agreement(users, reviews):
	"""Calculate Pearson correlation between each pair of users."""
	n = len(users)
	correlation_matrix = [[0.0] * n for _ in range(n)]
	
	for i, user_a in enumerate(users):
		for j, user_b in enumerate(users):
			if i == j:
				correlation_matrix[i][j] = 1.0
				continue
			
			# Find games both users rated
			pairs = []
			for entry in reviews:
				rating_a = entry["ratings"].get(user_a)
				rating_b = entry["ratings"].get(user_b)
				if rating_a is not None and rating_b is not None:
					pairs.append((rating_a, rating_b))
			
			if len(pairs) < 2:
				correlation_matrix[i][j] = 0.0
				continue
			
			# Calculate Pearson correlation
			ratings_a = [p[0] for p in pairs]
			ratings_b = [p[1] for p in pairs]
			
			mean_a = sum(ratings_a) / len(ratings_a)
			mean_b = sum(ratings_b) / len(ratings_b)
			
			numerator = sum((a - mean_a) * (b - mean_b) for a, b in pairs)
			sum_sq_a = sum((a - mean_a) ** 2 for a in ratings_a)
			sum_sq_b = sum((b - mean_b) ** 2 for b in ratings_b)
			denominator = (sum_sq_a * sum_sq_b) ** 0.5
			
			if denominator > 0:
				correlation_matrix[i][j] = numerator / denominator
			else:
				correlation_matrix[i][j] = 0.0
	
	return correlation_matrix


def build_tag_network(game_tags):
	"""Build network of tags that appear together in games."""
	G = nx.Graph()
	
	for game, info in game_tags.items():
		tags = info["tags"]
		# Filter out excluded tags
		filtered_tags = [tag for tag in tags if tag.strip().casefold() not in EXCLUDED_TAGS]
		# Add nodes
		for tag in filtered_tags:
			if tag not in G:
				G.add_node(tag)
		# Add edges between all tag pairs in this game
		for i, tag1 in enumerate(filtered_tags):
			for tag2 in filtered_tags[i+1:]:
				if G.has_edge(tag1, tag2):
					G[tag1][tag2]["weight"] += 1
				else:
					G.add_edge(tag1, tag2, weight=1)
	
	return G


def plot_tag_network(game_tags, output_path):
	"""Visualize tag co-occurrence network."""
	G = build_tag_network(game_tags)
	
	if len(G.nodes()) == 0:
		return
	
	plt.figure(figsize=(18, 14))
	# Use spring layout for better visualization
	pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
	
	# Color nodes by degree (number of connections)
	node_degrees = dict(G.degree())
	node_colors = [node_degrees[node] for node in G.nodes()]
	max_degree = max(node_degrees.values()) if node_degrees else 1
	
	# Draw nodes with color gradient based on degree
	nodes = nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=2000, 
	                                cmap="YlOrRd", vmin=0, vmax=max_degree, ax=plt.gca())
	
	# Draw edges with varying width based on weight
	edges = G.edges()
	weights = [G[u][v]["weight"] for u, v in edges]
	max_weight = max(weights) if weights else 1
	edge_widths = [3 * (w / max_weight) for w in weights]
	nx.draw_networkx_edges(G, pos, width=edge_widths, alpha=0.5, ax=plt.gca())
	
	# Draw labels with smaller font
	nx.draw_networkx_labels(G, pos, font_size=7, font_weight="bold", ax=plt.gca())
	
	plt.title("Tag Co-occurrence Network", fontsize=16, fontweight="bold")
	plt.axis("off")
	plt.tight_layout()
	plt.savefig(output_path, dpi=150, bbox_inches="tight")
	plt.close()


def plot_user_agreement_matrix(users, reviews, output_path):
	"""Create heatmap showing rating correlation between users."""
	correlation_matrix = compute_user_agreement(users, reviews)
	
	plt.figure(figsize=(8, 7))
	image = plt.imshow(correlation_matrix, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
	plt.colorbar(image, label="Correlation coefficient")
	plt.yticks(range(len(users)), users)
	plt.xticks(range(len(users)), users, rotation=45, ha="right")
	plt.title("User agreement matrix")
	
	# Add correlation values as text
	for i in range(len(users)):
		for j in range(len(users)):
			text = plt.text(j, i, f"{correlation_matrix[i][j]:.2f}",
						   ha="center", va="center", color="black", fontsize=10)
	
	plt.tight_layout()
	plt.savefig(output_path, dpi=150)
	plt.close()


def main():
	base_dir = os.path.dirname(os.path.abspath(__file__))
	reviews_path = os.path.join(base_dir, "reviews.csv")
	tags_path = os.path.join(base_dir, "gametags.json")

	game_tags = read_game_tags(tags_path)
	users, reviews = read_reviews(reviews_path)
	output_dir = os.path.join(base_dir, "outputs")
	os.makedirs(output_dir, exist_ok=True)

	tag_averages, tag_stats, unmatched = compute_tag_averages(
		users,
		reviews,
		game_tags,
		min_count=3,
	)
	plot_user_tags(tag_averages, output_dir, top_n=10)
	plot_tag_heatmap(
		tag_stats,
		users,
		os.path.join(output_dir, "tag_heatmap.png"),
		min_count=3,
	)
	plot_tag_counts_treemap(
		tag_stats,
		os.path.join(output_dir, "tag_counts_treemap.png"),
		min_count=3,
	)
	plot_user_agreement_matrix(users, reviews, os.path.join(output_dir, "user_agreement.png"))
	plot_tag_network(game_tags, os.path.join(output_dir, "tag_network.png"))

	if unmatched:
		print("Unmatched games (not found in gametags.json):")
		for name in sorted(set(unmatched)):
			print(f"- {name}")


if __name__ == "__main__":
	main()
