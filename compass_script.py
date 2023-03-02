import requests
import datetime
import uuid
import json
import uuid
import os
import sys

from datetime import datetime

LOGIN = sys.argv[1]
PASSWORD = sys.argv[2]  
PREF_PATH = sys.argv[3]

def getPreferences():
    f = open(PREF_PATH)
    data = json.load(f)
    f.close()
    return data

def evaluatePreference(meal_name, pref, point):
    tokens = pref.split('/')
    meal_name_insensitive_case = meal_name.lower()
    for token in tokens:
        if token.lower() not in meal_name_insensitive_case:
            return 0
    return point

def calculatePreferencePoint(preferences, meal_name, meal_attr):
    total_point = 0
    context_prefs = preferences['context_preferences']
    for pref, point in context_prefs.items():
        total_point += evaluatePreference( meal_name, pref, point)

    att_prefs = preferences['attribute_preferences']
    for pref, point in att_prefs.items():
        if pref in meal_attr:
            total_point += point

    return total_point

def authorize():
    url = 'https://mycompassfood.golunch.pl/GoLunch/Authorization.json'
    data = {'Brand': 'COMP', 'Login': LOGIN, 'Password': PASSWORD}
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()
    return response.json()['data']['access_token']

def get_ordered(token):
    url = 'https://mycompassfood.golunch.pl/GoLunch/GetOrderedMeals.json'
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain', 'Authorization': 'Bearer {}'.format(token)}
    data = {'LanguageSymbol': 'EN'}
    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()
    if 'DayList' in response.json()['data']:
        return response.json()['data']['DayList']
    else :
        return []

def get_meal_attribute(token, meal_id, meal_attr_dict):
    url = 'https://mycompassfood.golunch.pl/GoLunch/GetMealAttributes.json'
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain', 'Authorization': 'Bearer {}'.format(token) }
    data = {'LanguageSymbol': 'EN', 'MealID': meal_id}
    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()
    for mealData in response.json()['data']['MealList']:
        att_list = []
        for att in mealData['AttributeList']:
            if att['AttributeType'] == 0:
                att_list.append(att['AttributeValue'])
        meal_attr_dict[mealData['MealID']]  = sorted(att_list)
    return 

def print_ordered(token,myorders_list):
    preferences = getPreferences()
    meals = get_ordered(token)
    for mealData in meals:
        dt = datetime.strptime(mealData['Day'],'%Y-%m-%dT%H:%M:%S')
        print(dt.strftime('%A') + ' ('+ dt.strftime('%d/%m') + ')')
        myorders_list.append(dt.strftime('%d/%m'))
        for meal in mealData['OrderItemList']:
            print('\t' + meal['MealName'])
            for mealIteam in meal['OrderItemAdditionList']:
                print('\t\t> ' + mealIteam['Name'])
    return

def get_menu(token):
    url = 'https://mycompassfood.golunch.pl/GoLunch/GetMenu.json'
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain', 'Authorization': 'Bearer {}'.format(token)}
    data = {'LanguageSymbol': 'EN'}
    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()
    return response.json()['data']['MealDayList']

def get_pickup_location_and_time(token):
    url = 'https://mycompassfood.golunch.pl/GoLunch/GetPickupLocationAndTime.json'
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain', 'Authorization': 'Bearer {}'.format(token)}
    data = {'LanguageSymbol': 'EN'}
    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()
    result = {}
    for day_data in response.json()['data']['PickupDayList']:
        result[day_data['PickupDay']] = day_data['PickupLocationList'][0]['PickupTimeList'][0]['PickupTimeID']
    return result

def save_order(token, meal_day_id, additional_meal_id, dessert_id, pickup_time_id):
    url = 'https://mycompassfood.golunch.pl/GoLunch/SaveOrder.json'
    headers = {
        'accept': 'application/json, text/plain, */*',
        'authorization': 'Bearer {}'.format(token),
        'content-type': 'application/json',
    }
    order_id = str(uuid.uuid4())
    item_list = []

    if additional_meal_id != '':
        item = {}
        item['OrderItemID'] = order_id
        item['MealDayAdditionID'] = additional_meal_id
        item['SubsidizedValue'] = '0'
        item['PrepaidValue'] = '0'
        item['ToPayValue'] = '0'
        item_list.append(item)

    if dessert_id != "":
        item = {}
        item['OrderItemID'] = order_id
        item['MealDayAdditionID'] = dessert_id
        item['SubsidizedValue'] = '0'
        item['PrepaidValue'] = '0'
        item['ToPayValue'] = '0'
        item_list.append(item)

    data = {
        "OrderID": str(uuid.uuid4()),
        "OnlinePaymentEmail": "",
        "OrderItemList": {
            "OrderItem": 
            [
                {
                    "ID": order_id,
                    "MealDayID": meal_day_id,
                    "PickupTimeID": pickup_time_id,
                    "SubsidizedValue": "0.02",
                    "PrepaidValue": "0",
                    "ToPayValue": "0"
                }
            ]
        },
        "OrderItemAdditionList": {
            "OrderItemAddition": item_list
        },
        "LanguageSymbol": "EN"
    }
    print(json.dumps(data))
    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()
    return

def print_menu(token,myorders_list):
    meal_attr_dict = {}
    preferences = getPreferences()

    meals = get_menu(token)
    pickup_time_id = get_pickup_location_and_time(token)

    for mealData in meals:
        for meal in mealData['MealList']:
            for meal2 in meal['MealAdditionGroupList']:
                for meal3 in meal2['AdditionList']:
                    meal_id = meal3['ID']
                    get_meal_attribute(token, meal_id,meal_attr_dict)
            
    for mealData in meals:
        dessert_id = ""
        meal_total_pref_point = {}
        dt = datetime.strptime(mealData['Day'],'%Y-%m-%dT%H:%M:%S')
        date_key = dt.strftime('%d/%m')
        date_name = dt.strftime('%A')
        status = ''
        if myorders_list.count(date_key) > 0:
            status += ' [ORDERED]'
        if mealData['Day'] not in pickup_time_id:
            status += '[LATE]'

        print( date_name + ' ('+ date_key + ')' + status)
        if 'MealList' in mealData['MealList']:
            for meal in mealData['MealList']:
                for mealGroup in meal['MealAdditionGroupList']:
                    if "dessert" in mealGroup['Name']:
                        for singleMeal in mealGroup['AdditionList']:
                            print('\t> ' + singleMeal['Name'])
                            print('\t\t> ' + ','.join(meal_attr_dict[singleMeal['ID']]))
                            dessert_id = singleMeal['MealDayAdditionID']
                    else:
                        for singleMeal in mealGroup['AdditionList']:
                            print('\t> ' + singleMeal['Name'])
                            print('\t\t> ' + ','.join(meal_attr_dict[singleMeal['ID']]))
                            meal_total_pref_point[singleMeal['MealDayAdditionID']] = calculatePreferencePoint(preferences,singleMeal['Name'], meal_attr_dict[singleMeal['ID']])
                            print('\t\t> preference point =' + calculatePreferencePoint(preferences,singleMeal['Name'], meal_attr_dict[singleMeal['ID']]))
            if status == '':
                best_point = -1000000
                bestMealId = ''
                for meal_id, point in meal_total_pref_point.items():
                    if point > best_point:
                        best_point = point
                        bestMealId = meal_id
                save_order(token, meal['MealDayID'],  meal_id, dessert_id, pickup_time_id[mealData['Day'] ])

if __name__ == '__main__':
    myorders_list = []
    token = authorize()
    print(type(token).__name__ + ':' + token)
    print('###### ORDERED MEALS ######')
    print_ordered(token,myorders_list)
    print('###### MENU ######')
    print_menu(token,myorders_list)
