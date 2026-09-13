"""Smoke-check native graphs in a running Obsidian with its CLI enabled."""
import argparse
import base64
import os
import subprocess
from pathlib import Path


SCRIPT = r"""
(async () => {
  const bookmarks = app.internalPlugins.plugins.bookmarks.instance;
  const group = bookmarks.items.find(g => g.gurumoji === 'navigation');
  if (!group) throw Error('Gurumoji bookmarks missing');
  const leaf = app.workspace.getLeavesOfType('graph')[0] || app.workspace.getLeaf('tab');
  const cases = [group.items[1], ...group.items[3].items];
  const results = [];
  for (const bookmark of cases) {
    await bookmarks.openBookmarkInLeaf(bookmark, leaf);
    await new Promise(resolve => setTimeout(resolve, 1500));
    const actual = leaf.view.renderer.nodes.map(node => node.id).sort();
    const code = /tag:#interview\/([a-z0-9]+)/.exec(bookmark.options.search)?.[1];
    const expected = app.vault.getMarkdownFiles().filter(file => {
      const tags = app.metadataCache.getFileCache(file)?.frontmatter?.tags || [];
      if (!Array.isArray(tags) || tags.includes('graph/support') || tags.includes('graph/history')) return false;
      return code ? tags.includes('interview/' + code) && (tags.includes('graph/overview') || tags.includes('graph/detail'))
                  : tags.includes('graph/overview');
    }).map(file => file.path).sort();
    if (JSON.stringify(actual) !== JSON.stringify(expected)) throw Error('Graph does not match filter: ' + bookmark.title);
    results.push({view: code || 'overview', nodes: actual.length});
  }
  await bookmarks.openBookmarkInLeaf(group.items[1], leaf);
  app.workspace.setActiveLeaf(leaf, {focus: false});
  return JSON.stringify(results);
})()
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', default='ResearchVault')
    parser.add_argument('--cli', default=str(Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/Obsidian/Obsidian.com'))
    args = parser.parse_args()
    code = "eval(atob('" + base64.b64encode(SCRIPT.encode()).decode() + "'))"
    result = subprocess.run([args.cli, 'vault=' + args.vault, 'eval', 'code=' + code],
                            capture_output=True, text=True, encoding='utf-8', timeout=60)
    print(result.stdout)
    if result.returncode or 'Error:' in result.stdout or 'not enabled' in result.stdout:
        raise SystemExit(result.stderr or result.stdout or result.returncode)


if __name__ == '__main__':
    main()
