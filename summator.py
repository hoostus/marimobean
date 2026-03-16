# https://github.com/Ev2geny/evbeantools/blob/main/src/evbeantools/summator.py

"""
Implementation of the InventoryAggregator and BeanSummator classes
"""
from __future__ import annotations
import datetime
import re
from collections import defaultdict
from pprint import pprint
import copy
import logging
from pprint import pformat


from beancount.core.data import Transaction, Currency
from beancount.core.number import D
from beancount.core.position import Cost
from beancount.core.prices import PriceMap
from beancount.core import inventory
from beancount.loader import load_file
# importing beancount printer
from beancount.parser import printer
from beancount.core.account import root, Account
from beancount.core.convert import convert_amount, convert_position

from beancount.core.prices import build_price_map, PriceMap


# from pydantic import ValidationError, validate_call

# import pandas as pd

# type AccountsWithSum = defaultdict[Account,inventory.Inventory]

logger = logging.getLogger(__name__)

class InventoryAggregator(defaultdict):
    """
    Class which inherits from defaultdict and is used to hold account to inventory pairs
    Introduces some useful methods
    
    This is somehow similar to beancount Inventory class, but works with account to inventory pairs
    """
    def __init__(self, initiation_dict: None | dict[Account, str] = None):
        """
        Args:
          input (dict): Dictionary with account names as keys and strings
                         strings are the strings, which can be converted to Inventory objects using function 
                         inventory.from_string
        """
        super().__init__(inventory.Inventory)
        
        if initiation_dict:
            self._from_dict(initiation_dict)
        
        # pass
        # return super().__init__(inventory.Inventory)
    
    def sum_all(self) -> inventory.Inventory:
        """
        Sum all Inventories in all Account to Inventory pairs and returns the result as a new Inventory object
        """
        result = inventory.Inventory()
        
        for acc, inv in self.items():
            result.add_inventory(inv)
            
        return result
    
    def __sub__(self, other: InventoryAggregator) -> InventoryAggregator:
        """
        Subtract other from self and return a new InventoryAggregator object with the result
        """
        result = InventoryAggregator()
        
        # creating a set which contains all keys from self and other
        all_keys = set(self.keys()) | set(other.keys())
        
        for key in all_keys:
            result[key] =  -other[key] + self[key]
            
        return result
    
    def __copy__(self) -> InventoryAggregator:
        
        result = InventoryAggregator()
        
        for key, value in self.items():
            result[key] = copy.copy(value)
            
        return result
    
    def clean_empty(self) -> InventoryAggregator:
        """
        Removes all Account to Inventory pairs which have empty Inventory and 
        returns the result as a new InventoryAggregator object
        """
        result = InventoryAggregator()
        
        for acc, inv in self.items():
            if inv.is_empty():
                continue
            result[acc] = inv
        
        return result
    
    def is_empty(self) -> bool:
        """
        Returns True if all Inventories in the Account to Inventory pairs are empty
        """
        for inv in self.values():
            if not inv.is_empty():
                return False
        return True
    
    # @validate_call
    def convert(self, target_currency: Currency, price_map: PriceMap, date: datetime.date | None = None) -> InventoryAggregator:
        """
        Converts all Inventories in the Account to Inventory pairs to the target_currency
        
        returns:
                a new InventoryAggregator object with the result 
        """
        assert isinstance(target_currency, Currency)
        assert isinstance(price_map, PriceMap)
        assert isinstance(date, datetime.date) or date is None
        
        result = InventoryAggregator()
        
        logger.debug(f'self.items = \n{pformat(self.items())}')
        
        
        for acc, inv in self.items():
            # looping through all the inventories in the account to inventory pairs
            for pos in inv:
                
                # As the convert_position function removes the cost, we also lose the information about whether the 
                # position was tracked a cost or not. However this may be needed to be able to differenciate between   
                # unrealyzed gains, which ahapped in the assets tracked at cost and those which were not tracked at cost.
                # To work around this, we will create a dummy cost object, which will be added to all converted positions,
                # Which were originllay tracked at cost. The cost information will be just 1 unit of the "REMOVEDCOST" currency
                # So in a fact this acts more like a flag, that the position was tracked at cost, but the cost information was removed
                # Having the cost information identical for all such positions, will allow us to add and extract them from each other
                dummy_cost = None
                if pos.cost is not None:
                    dummy_cost = Cost(D("1"), "REMOVEDCOST", None, None)
                
                result[acc].add_amount(convert_position(pos, target_currency, price_map, date), dummy_cost)
            
        return result


    def currencies(self) -> set:
        """
        Returns a set of all currencies in the InventoryAggregator object
        """
        result = set()
        
        for inv in self.values():
            result |= inv.currencies()
        
        return result
    
    def get_currency_positions(self, currency: Currency) -> InventoryAggregator:
        """
        Returns a new InventoryAggregator object with the same account to inventory pairs as the original object,
        but with only the currency specified in the currency parameter
        Removes Account to Inventory pairs which do not have the specified currency
        """
        result = InventoryAggregator()
        
        for acc, inv in self.items():
            one_acc_result_inv = inventory.Inventory()
            for pos in inv:
                if pos.units.currency == currency:
                    one_acc_result_inv.add_amount(pos.units, pos.cost)
            # one_acc_result_inv.add_amount(inv.get_currency_units(currency))
            result[acc] = one_acc_result_inv
        
        result = result.clean_empty()
        
        return result
    
    def get_sorted(self):
        """ 
        Returns copy of itself, but sorted by account name.
        This is technically not needed, but is helpful, for debugging, when comparing 2 versions of beancount files
        """
        
        sorted_items = sorted(self.items())
        
        result = InventoryAggregator()
        
        for acc, inv in sorted_items:
            result[acc] = inv
            
        return result

    def _from_dict(self, input: dict):
        
        """
        Updates the InventoryAggregator object with the data from the input dictionary
        
        Args:
            input (dict): Dictionary with account names as keys and strings
                            strings are the strings, which can be converted to Inventory objects using function 
                            inventory.from_string
        """
        for account, inventory_str in input.items():
            assert not account in self, f'Something went wrong. The Account {account} is already in the InventoryAggregator object'
            
            self[account] = inventory.from_string(inventory_str)

    def is_small(self, tolerance) -> bool:
        """ Returns True if all Inventories in the Account to Inventory pairs as defined, by Inventory.is_small method
        
        Args:
          tolerances: A Decimal, the small number of units under which a position
            is considered small, or a dict of currency to such epsilon precision.
        
        Returns:
          A boolean.
        """
        for inv in self.values():
            if not inv.is_small(tolerance):
                return False
        return True
    
    def clean_small(self, tolerance) -> InventoryAggregator:
        """ Removes all Account to Inventory pairs which have small Inventories
        
        Args:
          tolerances: A Decimal, the small number of units under which a position
            is considered small, or a dict of currency to such epsilon precision.
        
        Returns:
          A new InventoryAggregator object with the result
        """
        
        result = InventoryAggregator()
        
        for acc, inv in self.items():
            if not inv.is_small(tolerance):
                result[acc] = inv
        
        return result   
    

class BeanSummator():
    """
       Simulates a beanquery SUM command for aggregating transaction amounts by account up to a specified 
       date as used in the below beanquetry query: 

        SELECT root(n, account) as shortened_acc, sum(position)
        WHERE date <= {date} AND account ~ "accounts_re"
        GROUP BY shortened_acc
        
        This class enhances efficiency by remembering the last sum calculated and the date for which it was calculated.
        It ensures that subsequent sums are requested for the same or later dates, allowing reuse of previous calculations.
        This approach speeds up the calculation process, especially beneficial when determining net worth across multiple dates.
    """
    def __init__(self, entries, options, accounts_re: str, num_acc_components_from_root: int = 100):
        """
        Initializes the BeanSummator with a set of entries, options, an account name pattern, and the number of account 
        levels to include.
        
        Parameters:
            entries (list): A list of beancount entries to process.
            options (dict): Options from the beancount file for processing.
            accounts_re (str): Regular expression pattern to filter accounts for summing.
            num_acc_components_from_root (int): Number of account hierarchy levels to retain in the account name.
                                                This is similar to the n in the root(n, account) function in the beanquery.
        """
        
        logger.debug(f'Creating BeanSummator with accounts_re={accounts_re} and num_acc_components_from_root={num_acc_components_from_root}')
        
        self.entries = entries
        self.options = options
        # self.current_sum = AccountsWithSum(inventory.Inventory)
        self.current_sum = InventoryAggregator()
        self.last_processed_date = datetime.date(1, 1, 1)
        self.entries_iter = iter(entries)
        self.unprocessed_entry_from_last_run = None
        self.accounts_re = accounts_re
        self.num_acc_components_from_root = num_acc_components_from_root
        
    def _get_copy_current_sum(self) -> InventoryAggregator:
        """
        Returns a copy of the current sum
        """
        return copy.copy(self.current_sum)
    
    def sum_till_date(self, date: datetime.date) -> InventoryAggregator:
        """
        Sums the balances of transactions for accounts matching the accounts_re regular expression pattern up and 
        including to the specified date.
        
        Parameters:
            date (datetime.date): The date up to and including which to sum transactions.
        
        Returns:
            AccountsWithInventories: The sum of transactions grouped by account up to the specified date.
        
        Raises:
            ValueError: If the requested date is before the last processed date.
        """
        
        logger.debug(f'Calculating sum for date {date}')
        
        assert isinstance(date, datetime.date)
        
        if date < self.last_processed_date:
            raise ValueError(f'Date {date} is in the past of the last date the summation was requested for {self.last_processed_date}')
        
        if self.unprocessed_entry_from_last_run:
            # If there is an unprocessed entry from the last run, we must process it first
            # but only if it is before or equal to the requested date
            if self.unprocessed_entry_from_last_run.date <= date:
                logger.debug(f'Processing unprocessed entry from the last run')
                self._process_entry(self.unprocessed_entry_from_last_run)
                self.unprocessed_entry_from_last_run = None
                
            else:
                # If the unprocessed entry is after the requested date, that means, that the new date is after or equal to the 
                # last processed date, but before the unprocessed entry. In another words there are no entries between last processed date
                # and a new requested date. In this case, we can return the current sum.
                result = self._get_copy_current_sum()
                logger.debug(f'No new sum is calculated. Returned result is \n {pformat(result)}')
                return result
    
        while True:
            try:
                entry = next(self.entries_iter)
                logger.debug(f'Looking at the entry \n {pformat(entry)}')
                if entry.date > date:
                    # Knowing that all beancount entries must be sorted by date, if this situation occurs, it means that we have
                    # all ready processed all entries untill including the requested date and have already passed it
                    # hence we must stop the iteration, but save the last entry for the next time the method is called
                    self.unprocessed_entry_from_last_run = entry
                    logger.debug(f'Unprocessed entry is saved for the next run')
                    break
                # Otherwise just process the entry
                self._process_entry(entry)
            except StopIteration:
                break
        
        self.last_processed_date = date
        
        result = self._get_copy_current_sum()
        logger.debug(f'Calculated sum is \n {pformat(result)}')
        return result
            
    def _process_entry(self, entry):
        """
        Process the entry and update the current_sum
        """
        
        logger.debug(f'Processing entry \n {pformat(entry)}')
        
        if isinstance(entry, Transaction):
            for posting in entry.postings:
                if re.search(self.accounts_re, posting.account):
                    shortened_account = root(self.num_acc_components_from_root, posting.account)
                    self.current_sum[shortened_account].add_amount(posting.units, posting.cost)

        
        
if __name__ == '__main__':
   pass

    
