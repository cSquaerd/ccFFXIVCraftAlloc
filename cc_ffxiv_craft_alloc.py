#!/bin/python3
import argparse, enum, json, random

class Crystal(enum.StrEnum):
	"""
	Representation of the elemental crystals needed as fuel for crafting.
	The optional colorized_name() method can be used for colored output.
	"""

	FIRE = 'F'
	ICE = 'I'
	WIND = 'W'
	EARTH = 'E'
	LIGHTNING = 'L'
	WATER = 'A'

	def __lt__(self, other) -> bool:
		sorting_dict = {'F': 0, 'I': 1, 'W': 2, 'E': 3, 'L': 4, 'A': 5}
		return sorting_dict[self] < sorting_dict[other]

	def colorized_name(self) -> str:
		color_codes = {'F': "101", 'I': "106", 'W': "102", 'E': "103", 'L': "105", 'A': "104"}
		return "\x1B[{:s}m{:s}\x1B[0m".format(color_codes[self.value], self.name.capitalize())

class Ingredient(enum.StrEnum):
	"""
	Representation of the generic ingredient types.

	In general, STONE means whichever whetstone is high level,
	ALCHEMIC means whichever ink (for SCH/SMN/PCT) is high level,
	and FOOD means whichever mob dropped food is high level;
	This should hold for everything Stormblood and up, more or less.

	The main 5 materials should be self-evident as to which
	particular item they represent per expansion.
	"""

	LUMBER = 'W',
	LEATHER = 'L'
	GEM = 'G',
	CLOTH = 'C',
	INGOT = 'I',
	STONE = 'S'
	ALCHEMIC = 'A',
	FOOD = 'F'

	def __lt__(self, other) -> bool:
		sorting_dict = {'W': 0, 'L': 1, 'G': 2, 'C': 4, 'I': 5, 'S': 3, 'A': 6, 'F': 7}
		return sorting_dict[self] < sorting_dict[other]

class CollectableRecipe:
	"""
	Structure for describing a crafting recipe for a collectable item.

	Can be for the latest expansion scrip currency or an older one.
	"""

	def __init__(
		self, name : str = "", ingredients : list[tuple[Ingredient, int]] = [], crystals : list[tuple[Crystal, int]] = []
	):
		"""
		Primary constructor, takes explicit lists of Ingredient-count and Crystal-count pairs, as well as a name.
		"""

		self.name = name
		self.ingredients = dict()
		for i, count in ingredients:
			self.ingredients[i] = count

		self.crystals = dict()
		for e, count in crystals:
			self.crystals[e] = count
		
	def __str__(self) -> str:
		return "[{: ^24s}]\n".format(self.name) + '\n'.join(
			[
				"  Ingr: {: >10s} ({: ^3d})".format(k.name.capitalize(), self.ingredients[k])
				for k in sorted(sorted(self.ingredients.keys()), key = lambda i : self.ingredients[i], reverse = True)
			] + [ # We use 20 instead of 10 to account for the char overhead from colorized_name's ANSI escape chars
				"  Crys: {: >20s} ({: ^3d})".format(k.colorized_name(), self.crystals[k])
				for k in sorted(sorted(self.crystals.keys()), key = lambda c : self.crystals[c], reverse = True)
			]
		)
	def __repr__(self) -> str:
		return str(self)		

	def from_string(self, signature : str) -> "CollectableRecipe":
		"""
		Quick constructor. signature follows the format output by to_signature(),
		see its documentation for details.
		"""

		try:
			name, ingredients_untokenized, crystals_untokenized = signature.split(';')
			
			ingredients_tokenized = list(
				map(
					lambda s : (Ingredient(s[0]), int(s[1:])), ingredients_untokenized.split(',')
				)
			)
			crystals_tokenized = list(
				map(
					lambda s : (Crystal(s[0]), int(s[1:])), crystals_untokenized.split(',')
				)
			)

			new_ingredients = {t[0] : t[1] for t in ingredients_tokenized}
			new_crystals = {t[0] : t[1] for t in crystals_tokenized}

			self.name = name
			self.ingredients = new_ingredients
			self.crystals = new_crystals
		except ValueError as ve:
			print("Could not construct recipe, ValueError: <{}>".format(ve))
		except IndexError as ie:
			print("Could not construct recipe, IndexError: <{}>".format(ie))

		return self
	
	def to_signature(self) -> str:
		"""
		Create a signature string that describes the recipe as succinctly as possible.

		There are three main fields that are semicolon separated:
		* The name of the recipe
		* The ingredients, which are comma-separated letter-number pairs, where:
		  * The letter corresponds to the Ingredient enum value letter
		  * The number is the count of how much of the Ingredient is needed for the recipe
		* The crystals, which are too comma-separated letter-number pairs,
		  like the ingredients are detailed above

		Ex. "fishing rod;W2,G1,I1;W8,I8" represents the level 100 recipe for the
		Rarefied Claro Walnut Fishing Rod

		Note that as long as ingredients remain in the middle and crystals on the right,
		relative to the semicolons, their order between the commas does not matter.
		"""

		return "{:s};{:s};{:s}".format(
			self.name,
			','.join(k.value + str(self.ingredients[k]) for k in sorted(self.ingredients.keys())),
			','.join(k.value + str(self.crystals[k]) for k in sorted(self.crystals.keys()))
		)

	def overlap(self, other) -> tuple[list[Ingredient], list[Crystal]]:
		"""
		Determine which Ingredients and Crystals overlap between two recipes.
		"""
		return (
			[i for i in Ingredient if i in self.ingredients and i in other.ingredients],
			[c for c in Crystal if c in self.crystals and c in other.crystals]
		)

class RecipeCollection:
	"""
	Structure for comparing two or more recipes, and estimating optimal allocations
	given budget restrictions via Monte Carlo methods.
	"""
	def __init__(self, recipes : list[CollectableRecipe]):
		"""
		Primary Constructor. It is recommended to build up from signature strings.
		"""

		self.recipes = recipes

	def __str__(self) -> str:
		return str(list(map(lambda r : r.name, self.recipes)))

	def summarize(self, counts : list[int]) -> dict[str, dict[str, int]]:
		"""
		Given a count of how much of each recipe will be produced,
		return a dictionary with the totals of each ingredient and crystal.
		"""

		summary = dict()
		if len(counts) != len(self.recipes):
			print("Error: size mismatch of counts parameter ({:d} vs. {:d})".format(len(counts), len(self.recipes)))
			return summary

		summary["ingredients"] = dict()
		summary["crystals"] = dict()

		for i in Ingredient:
			summary["ingredients"][i] = 0
			
			for n in range(len(self.recipes)):
				r = self.recipes[n]
				k = counts[n]
				if i in r.ingredients:
					summary["ingredients"][i] += k * r.ingredients[i]

		for c in Crystal:
			summary["crystals"][c] = 0

			for n in range(len(self.recipes)):
				r = self.recipes[n]
				k = counts[n]
				if c in r.crystals:
					summary["crystals"][c] += k * r.crystals[c]

		return summary
	
	def approximate_counts(
		self, budget_ingredients : dict[Ingredient, int], budget_crystals : dict[Crystal, int],
		max_rounds : int = 1_000, failures_until_stop : int = 50, debug_print : bool = False
	) -> list[int]:
		"""
		Primary stage Monte Carlo method.

		Given a budget of each ingredient and crystal, create a zero-vector of recipe production counts.
		Randomly increment each recipe's count, backtracking if it goes over-budget.
		Stop when either max_rounds iterations have occurred or if failures_until_stop backtracks in a row occurred.
		"""

		def valid_bill(
			summary : dict[str, dict[str, int]], budget_i : dict[Ingredient, int], budget_c : dict[Crystal, int]
		) -> bool:
			"""
			Helper function that checks if the current count vector would go over-budget.
			"""

			for i in Ingredient:
				if summary["ingredients"][i] > budget_i[i]:
					if debug_print:
						print(i, "over-budgeted")
					return False
			for c in Crystal:
				if summary["crystals"][c] > budget_c[c]:
					if debug_print:
						print(c, "over-budgeted")
					return False

			return True
		
		counts = [0 for r in self.recipes]

		failure_streak = 0
		rounds = 0
		n_recipes = len(self.recipes) - 1
		
		while rounds < max_rounds and failure_streak < failures_until_stop:
			i_recipe = random.randint(0, n_recipes)
			counts[i_recipe] += 1

			summary = self.summarize(counts)
			if not valid_bill(summary, budget_ingredients, budget_crystals):
				counts[i_recipe] -= 1
				failure_streak += 1
				if debug_print:
					print("Failed on", self.recipes[i_recipe].name, "increase, fail streak", failure_streak)
			else:
				failure_streak = 0
				if debug_print:
					print(self.recipes[i_recipe].name, counts)

		if debug_print:
			print(rounds, failure_streak)
		
		return counts
		
	def meta_approximate(
		self, budget_ingredients : dict[Ingredient, int], budget_crystals : dict[Crystal, int],
		max_rounds : int = 1_000, failures_until_stop : int = 50, max_approximations : int = 100,
		debug_print : bool = False, debug_print_inner : bool = False
	) -> tuple[int, list[list[int]]]:
		"""
		Secondary stage Monte Carlo method.

		Run the primary stage many times, logging which returned vectors yield the highest production count.
		On ties, collect alternate vectors. On a new maximum, drop all old vectors.
		After all primary stage runs are complete, return the production count and count vector.
		"""

		max_items = 0
		max_vectors = []

		for n in range(max_approximations):
			approx = self.approximate_counts(
				budget_ingredients, budget_crystals, max_rounds, failures_until_stop, debug_print_inner
			)

			if sum(approx) > max_items:
				if debug_print:
					print("Found a new maximum count! {:d} > {:d}, <{}>".format(sum(approx), max_items, approx))
				max_items = sum(approx)
				max_vectors = [approx]
			elif sum(approx) == max_items:
				if debug_print:
					print("Found a new maximal vector! {:d} now known, <{}>".format(len(max_vectors) + 1, approx))
				max_vectors.append(approx)

		if debug_print:
			print("Maximum count was {:d} with {:d} maximal vectors.".format(max_items, len(max_vectors)))
		return (max_items, max_vectors)

def main():
	parser = argparse.ArgumentParser(
		description = "Crafting Recipe Allocator and Budget Checker for Final Fantasy XIV, specifically for Collectables",
		formatter_class = argparse.RawTextHelpFormatter
	)

	parser.add_argument("manifest", help = "Path to JSON detailing recipes and budget")

	argv = parser.parse_args()

	try:
		with open(argv.manifest, 'r') as f:
			manifest = json.load(f)
	except FileNotFoundError as fnfe:
		print("Bad filename: <{}>".format(fnfe))
		exit(1)

	recipes = None
	if "signatures" in manifest["recipes"].keys():
		recipes = list(map(lambda sig : CollectableRecipe().from_string(sig), manifest["recipes"]["signatures"]))

	if recipes is None:
		print("Could not construct recipes.")
		exit(1)

	budget_ingredients = None
	budget_crystals = None

	if "ingredients" in manifest["budget"].keys():
		budget_ingredients = {
			Ingredient(k): manifest["budget"]["ingredients"][k] for k in manifest["budget"]["ingredients"].keys()
		}

	if "crystals" in manifest["budget"].keys():
		budget_crystals = {
			Crystal(k): manifest["budget"]["crystals"][k] for k in manifest["budget"]["crystals"].keys()
		}

	if budget_ingredients is None or budget_crystals is None:
		print("Could not retrieve budgets.")
		exit(1)

	R = RecipeCollection(recipes)

	production_count, best_vectors = R.meta_approximate(
		budget_ingredients, budget_crystals, debug_print = True, debug_print_inner = False
	)

	print(
		"{:d} collectables can be produced with the following allocation: \n\t{:s}".format(
			production_count,
			"\n\t".join(
				[
					"({: >4d}) {: >24s}".format(best_vectors[0][i], R.recipes[i].name)
					for i in range(len(R.recipes))
				]
			)
		)
	)

	if len(best_vectors) > 1:
		print("Other count vectors are: \n\t{:s}".format("\n\t".join([str(v) for v in best_vectors])))

if __name__ == "__main__":
	main()

