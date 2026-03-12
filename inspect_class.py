from pytgcalls import PyTgCalls
import inspect

def main():
    print("Methods in PyTgCalls class:")
    methods = [m for m, _ in inspect.getmembers(PyTgCalls, predicate=inspect.isfunction)]
    # Also check for async functions (coroutines) which might be wrapped
    # but inspect.isfunction should catch most
    for method in sorted(methods):
        if not method.startswith("_"):
            print(f" - {method}")
            
    # Also check properties or other members
    print("\nAll public members:")
    for name, obj in inspect.getmembers(PyTgCalls):
        if not name.startswith("_"):
            print(f" - {name} ({type(obj)})")

if __name__ == "__main__":
    main()
