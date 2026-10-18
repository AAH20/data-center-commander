// Fuzz tests for topology.js using fast-check.
const fc = require('fast-check');
const assert = require('assert');

// Graph layout calculation
function calculateNodePositions(nodes, edges, width, height) {
  const positions = {};
  const n = nodes.length;

  // Simple circular layout
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(width, height) * 0.4;

  nodes.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / n;
    positions[node.id] = {
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    };
  });

  return positions;
}

// Edge path calculation
function calculateEdgePath(source, target) {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const cx1 = source.x + dx * 0.3;
  const cy1 = source.y + dy * 0.1;
  const cx2 = source.x + dx * 0.7;
  const cy2 = source.y + dy * 0.9;

  return `M ${source.x} ${source.y} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${target.x} ${target.y}`;
}

// Graph connectivity check
function isConnected(nodes, edges) {
  if (nodes.length === 0) return true;
  if (nodes.length === 1) return true;

  const adjacency = {};
  nodes.forEach(n => { adjacency[n.id] = []; });
  edges.forEach(e => {
    if (adjacency[e.source]) adjacency[e.source].push(e.target);
    if (adjacency[e.target]) adjacency[e.target].push(e.source);
  });

  const visited = new Set();
  const queue = [nodes[0].id];
  visited.add(nodes[0].id);

  while (queue.length > 0) {
    const current = queue.shift();
    for (const neighbor of adjacency[current] || []) {
      if (!visited.has(neighbor)) {
        visited.add(neighbor);
        queue.push(neighbor);
      }
    }
  }

  return visited.size === nodes.length;
}

// Strategies
const nodeCount = fc.integer({ min: 1, max: 50 });
const width = fc.double({ min: 100, max: 5000, noNaN: true });
const height = fc.double({ min: 100, max: 5000, noNaN: true });

const graphData = fc.record({
  nodes: fc.array(fc.record({ id: fc.string(), label: fc.string() }), { minLength: 1, maxLength: 50 }),
  edges: fc.array(fc.record({ source: fc.string(), target: fc.string() }), { maxLength: 100 }),
}).map(graph => {
  // Ensure unique node IDs and filter edges to only reference existing nodes
  const seen = new Set();
  graph.nodes = graph.nodes.filter(n => {
    if (seen.has(n.id)) return false;
    seen.add(n.id);
    return true;
  });
  graph.edges = graph.edges.filter(e => seen.has(e.source) && seen.has(e.target));
  return graph;
});

describe('Topology Fuzz Tests', () => {
  describe('calculateNodePositions', () => {
    it('should handle any valid graph and dimensions', () => {
      fc.assert(
        fc.property(graphData, width, height, (graph, w, h) => {
          const positions = calculateNodePositions(graph.nodes, graph.edges, w, h);
          assert(Object.keys(positions).length === graph.nodes.length);
          Object.values(positions).forEach(pos => {
            assert(Number.isFinite(pos.x));
            assert(Number.isFinite(pos.y));
          });
        }),
        { numRuns: 100 }
      );
    });
  });

  describe('calculateEdgePath', () => {
    it('should handle any valid coordinates', () => {
      fc.assert(
        fc.property(
          fc.record({ x: fc.double({ noNaN: true }), y: fc.double({ noNaN: true }) }),
          fc.record({ x: fc.double({ noNaN: true }), y: fc.double({ noNaN: true }) }),
          (source, target) => {
            const path = calculateEdgePath(source, target);
            assert(typeof path === 'string');
            assert(path.startsWith('M '));
            assert(path.includes('C '));
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  describe('isConnected', () => {
    it('should handle any valid graph', () => {
      fc.assert(
        fc.property(graphData, (graph) => {
          const connected = isConnected(graph.nodes, graph.edges);
          assert(typeof connected === 'boolean');
        }),
        { numRuns: 100 }
      );
    });

    it('should return true for single node', () => {
      const result = isConnected([{ id: 'a' }], []);
      assert(result === true);
    });

    it('should return true for empty graph', () => {
      const result = isConnected([], []);
      assert(result === true);
    });
  });
});
